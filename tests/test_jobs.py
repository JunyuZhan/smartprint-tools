# -*- coding: utf-8 -*-
"""JobManager 任务队列测试：状态流转、失败路径、清理逻辑。

打印机与文件转换全部 mock，数据目录隔离到 tmp_path。
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from smartprint.jobs import JobManager


@pytest.fixture
def fake_env(tmp_path, monkeypatch):
    """mock 打印机与转换器，返回 JobManager"""
    import smartprint.printer as printer_mod
    monkeypatch.setattr(printer_mod, "resolve_printer", lambda name: name or "FAKE-PRINTER")
    monkeypatch.setattr(printer_mod, "print_pdf", lambda *a, **k: None)

    import smartprint.converters as conv_mod
    monkeypatch.setattr(conv_mod, "ensure_pdf", lambda src, td: src)

    cfg = {
        "printer": "FAKE-PRINTER",
        "_tmp_dir": str(tmp_path),
        "clean_days": 7,
    }
    return tmp_path, cfg


def _wait_status(mgr, jid, *want, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = mgr.get(jid)
        if job and job["status"] in want:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {jid} 超时未达到 {want}，当前={mgr.get(jid)}")


def test_add_upload_and_get(fake_env):
    tmp, cfg = fake_env
    mgr = JobManager(cfg)
    src = tmp / "a.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    job = mgr.add_upload(src, "a.pdf", src.stat().st_size)
    assert job["status"] == "uploaded"
    assert job["name"] == "a.pdf"
    got = mgr.get(job["id"])
    assert got["id"] == job["id"]
    assert mgr.get("nope") is None


def test_enqueue_and_done(fake_env):
    tmp, cfg = fake_env
    mgr = JobManager(cfg)
    src = tmp / "a.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    job = mgr.add_upload(src, "a.pdf", src.stat().st_size)
    assert mgr.enqueue(job["id"], {"color": "mono"}) is True
    done = _wait_status(mgr, job["id"], "done")
    assert done["printer"] == "FAKE-PRINTER"
    assert done["settings"]["color"] == "mono"
    assert done["finished"]


def test_enqueue_unknown_job(fake_env):
    tmp, cfg = fake_env
    mgr = JobManager(cfg)
    assert mgr.enqueue("nope", {}) is False


def test_print_failure_sets_failed(fake_env, monkeypatch):
    tmp, cfg = fake_env
    import smartprint.printer as printer_mod

    def boom(*a, **k):
        raise RuntimeError("模拟打印失败：纸张卡住")

    monkeypatch.setattr(printer_mod, "print_pdf", boom)
    mgr = JobManager(cfg)
    src = tmp / "a.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    job = mgr.add_upload(src, "a.pdf", src.stat().st_size)
    assert mgr.enqueue(job["id"], {}) is True
    failed = _wait_status(mgr, job["id"], "failed")
    assert "纸张卡住" in failed["error"]
    assert failed["finished"]


def test_conversion_failure_sets_failed(fake_env, monkeypatch):
    tmp, cfg = fake_env
    import smartprint.converters as conv_mod

    def bad_convert(*a, **k):
        raise RuntimeError("不支持的文件类型")

    monkeypatch.setattr(conv_mod, "ensure_pdf", bad_convert)
    mgr = JobManager(cfg)
    src = tmp / "a.xyz"
    src.write_bytes(b"bad")
    job = mgr.add_upload(src, "a.xyz", src.stat().st_size)
    assert mgr.enqueue(job["id"], {}) is True
    failed = _wait_status(mgr, job["id"], "failed")
    assert "不支持的文件类型" in failed["error"]


def test_remove_rules(fake_env):
    tmp, cfg = fake_env
    mgr = JobManager(cfg)
    src = tmp / "a.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    # uploaded 可删
    job = mgr.add_upload(src, "a.pdf", src.stat().st_size)
    assert mgr.remove(job["id"]) is True
    # 不存在不可删
    assert mgr.remove("nope") is False
    # queued 不可删（直接构造状态，避免 worker 线程竞态）
    job2 = mgr.add_upload(src, "b.pdf", src.stat().st_size)
    mgr._set(job2["id"], status="queued")
    assert mgr.remove(job2["id"]) is False
    # printing 不可删
    job3 = mgr.add_upload(src, "c.pdf", src.stat().st_size)
    mgr._set(job3["id"], status="printing")
    assert mgr.remove(job3["id"]) is False


def test_list_all_sorted_by_created(fake_env):
    tmp, cfg = fake_env
    mgr = JobManager(cfg)
    src = tmp / "a.pdf"
    src.write_bytes(b"%PDF-1.4 test")
    j1 = mgr.add_upload(src, "a.pdf", 1)
    mgr._set(j1["id"], created="2026-01-01 10:00:00")
    j2 = mgr.add_upload(src, "b.pdf", 2)
    mgr._set(j2["id"], created="2026-01-01 10:00:01")
    lst = mgr.list_all()
    assert [j["id"] for j in lst] == [j2["id"], j1["id"]]


def test_cleanup_removes_expired(fake_env):
    tmp, cfg = fake_env
    cfg["clean_days"] = 1
    mgr = JobManager(cfg)
    old = tmp / "old.pdf"
    old.write_bytes(b"%PDF-1.4 old")
    # 把 mtime 改成 3 天前
    import os
    old_ts = time.time() - 3 * 86400
    os.utime(old, (old_ts, old_ts))
    job = mgr.add_upload(old, "old.pdf", old.stat().st_size)
    mgr._set(job["id"], status="done")
    fresh = tmp / "fresh.pdf"
    fresh.write_bytes(b"%PDF-1.4 fresh")
    job2 = mgr.add_upload(fresh, "fresh.pdf", fresh.stat().st_size)
    mgr.cleanup()
    assert mgr.get(job["id"]) is None
    assert not old.exists()
    assert mgr.get(job2["id"]) is not None
    assert fresh.exists()


def test_cleanup_keeps_queued(fake_env):
    """队列中的任务即使过期也不清理（防止正在打印的文件被删）"""
    tmp, cfg = fake_env
    cfg["clean_days"] = 1
    mgr = JobManager(cfg)
    import os
    old = tmp / "queued.pdf"
    old.write_bytes(b"%PDF-1.4 q")
    old_ts = time.time() - 3 * 86400
    os.utime(old, (old_ts, old_ts))
    job = mgr.add_upload(old, "queued.pdf", old.stat().st_size)
    mgr._set(job["id"], status="queued")
    mgr.cleanup()
    assert mgr.get(job["id"]) is not None
    assert old.exists()
