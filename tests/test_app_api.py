# -*- coding: utf-8 -*-
"""Web API 集成测试：Flask test client 覆盖全部路由。

打印机与文件转换全部 mock（不碰真实打印机 / 外部进程），
数据目录隔离到 pytest tmp_path，不污染项目目录。
"""
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PIL import Image

from smartprint import config
from smartprint.app import create_app


def _png_bytes(size: int = 10) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def make_app(tmp_path, monkeypatch):
    # 隔离数据目录与配置文件（防止测试污染真实 config.json / data / logs）
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "data" / "uploads")
    monkeypatch.setattr(config, "TMP_DIR", tmp_path / "data" / "tmp")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "data" / "state.json")

    # mock 打印机与转换器
    import smartprint.printer as printer_mod
    monkeypatch.setattr(printer_mod, "list_printers", lambda: ["Canon MG3000"])
    monkeypatch.setattr(printer_mod, "resolve_printer", lambda name: name or "Canon MG3000")
    monkeypatch.setattr(printer_mod, "print_pdf", lambda *a, **k: None)
    monkeypatch.setattr(printer_mod, "print_test_page", lambda *a, **k: None)

    import smartprint.converters as conv_mod
    monkeypatch.setattr(conv_mod, "ensure_pdf", lambda src, td: src)

    def _make(**overrides):
        cfg = {
            "_secret": "test-secret",
            "office_name": "测试办公室",
            "max_upload_mb": 2,
            "access_mode": "lan",
            "print_defaults": {"color": "color", "duplex": "single", "copies": 1, "pages": ""},
        }
        cfg.update(overrides)
        app_obj = create_app(cfg)
        app_obj.config["TESTING"] = True
        return app_obj

    return _make


def _wait_job(client, jid, timeout=10):
    """轮询任务直到 done/failed"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/job/{jid}")
        assert r.status_code == 200
        job = r.get_json()["job"]
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {jid} 超时未完成")


# ---------- 页面 ----------

def test_index_page(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "text/html" in r.content_type
        assert len(r.data) > 0


def test_admin_page_loopback_only(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.get("/admin")
        assert r.status_code == 200
        # 模拟非本机访问 → 403
        r2 = c.get("/admin", environ_overrides={"REMOTE_ADDR": "192.168.1.50"})
        assert r2.status_code == 403


# ---------- 公共配置 ----------

def test_api_config(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.get("/api/config")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["office_name"] == "测试办公室"
        assert data["printers"] == ["Canon MG3000"]
        assert data["max_upload_mb"] == 2
        assert data["pin_required"] is False


# ---------- 上传 ----------

def test_upload_requires_file(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.post("/api/upload")
        assert r.status_code == 400


def test_upload_single_file(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.post("/api/upload", data={"file": (io.BytesIO(_png_bytes()), "a.png")},
                   content_type="multipart/form-data")
        assert r.status_code == 200
        jobs = r.get_json()["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["name"] == "a.png"
        assert jobs[0]["status"] == "uploaded"


def test_upload_multiple_files(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.post("/api/upload", data={"file": [
            (io.BytesIO(_png_bytes()), "a.png"),
            (io.BytesIO(_png_bytes()), "b.jpg"),
        ]}, content_type="multipart/form-data")
        assert r.status_code == 200
        assert len(r.get_json()["jobs"]) == 2


def test_upload_unsafe_filename_sanitized(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.post("/api/upload", data={"file": (io.BytesIO(_png_bytes()), "../..\\evil<>.png")},
                   content_type="multipart/form-data")
        assert r.status_code == 200
        name = r.get_json()["jobs"][0]["name"]
        assert "/" not in name and "\\" not in name and "<" not in name and ">" not in name
        assert name == "evil__.png"


def test_upload_too_large(make_app):
    app = make_app()
    with app.test_client() as c:
        big = io.BytesIO(b"\x00" * (3 * 1024 * 1024))  # 3MB > 2MB 限制
        r = c.post("/api/upload", data={"file": (big, "big.bin")},
                   content_type="multipart/form-data")
        assert r.status_code == 413


# ---------- 打印 ----------

def test_print_requires_job_ids(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.post("/api/print", json={})
        assert r.status_code == 400


def test_print_uploaded_job_done(make_app):
    app = make_app()
    with app.test_client() as c:
        up = c.post("/api/upload", data={"file": (io.BytesIO(_png_bytes()), "a.png")},
                    content_type="multipart/form-data")
        jid = up.get_json()["jobs"][0]["id"]
        r = c.post("/api/print", json={"job_ids": [jid], "settings": {"color": "mono", "copies": 1}})
        assert r.status_code == 200
        data = r.get_json()
        assert data["job_ids"] == [jid]
        assert data["settings"]["color"] == "mono"
        job = _wait_job(c, jid)
        assert job["status"] == "done"


def test_print_settings_merge_defaults(make_app):
    app = make_app()
    with app.test_client() as c:
        up = c.post("/api/upload", data={"file": (io.BytesIO(_png_bytes()), "a.png")},
                    content_type="multipart/form-data")
        jid = up.get_json()["jobs"][0]["id"]
        # 只传 color，其余沿用默认
        r = c.post("/api/print", json={"job_ids": [jid], "settings": {"color": "mono"}})
        data = r.get_json()
        assert data["settings"]["color"] == "mono"
        assert data["settings"]["duplex"] == "single"
        assert data["settings"]["copies"] == 1
        # copies 边界：0 → 1，100 → 99
        r2 = c.post("/api/print", json={"job_ids": [jid], "settings": {"copies": 0}})
        assert r2.get_json()["settings"]["copies"] == 1
        r3 = c.post("/api/print", json={"job_ids": [jid], "settings": {"copies": 100}})
        assert r3.get_json()["settings"]["copies"] == 99


def test_print_unknown_job_ignored(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.post("/api/print", json={"job_ids": ["nonexistent"]})
        assert r.status_code == 200
        assert r.get_json()["job_ids"] == []


# ---------- 任务列表 / 查询 / 删除 ----------

def test_jobs_list_and_get(make_app):
    app = make_app()
    with app.test_client() as c:
        up = c.post("/api/upload", data={"file": (io.BytesIO(_png_bytes()), "a.png")},
                    content_type="multipart/form-data")
        jid = up.get_json()["jobs"][0]["id"]
        lst = c.get("/api/jobs").get_json()["jobs"]
        assert any(j["id"] == jid for j in lst)
        got = c.get(f"/api/job/{jid}").get_json()["job"]
        assert got["id"] == jid
        assert c.get("/api/job/nope").status_code == 404


def test_job_delete(make_app, monkeypatch):
    app = make_app()
    with app.test_client() as c:
        up = c.post("/api/upload", data={"file": (io.BytesIO(_png_bytes()), "a.png")},
                    content_type="multipart/form-data")
        jid = up.get_json()["jobs"][0]["id"]
        assert c.delete(f"/api/job/{jid}").status_code == 200
        assert c.get(f"/api/job/{jid}").status_code == 404
        # 打印中/排队中不可删除：用阻塞的 print mock 保证任务停在打印中（消除 worker 竞态）
        import smartprint.printer as printer_mod
        import threading
        gate = threading.Event()

        def blocked_print(*a, **k):
            gate.wait(5)

        monkeypatch.setattr(printer_mod, "print_pdf", blocked_print)
        up2 = c.post("/api/upload", data={"file": (io.BytesIO(_png_bytes()), "b.png")},
                     content_type="multipart/form-data")
        jid2 = up2.get_json()["jobs"][0]["id"]
        c.post("/api/print", json={"job_ids": [jid2]})
        r = c.delete(f"/api/job/{jid2}")
        assert r.status_code == 400
        gate.set()


# ---------- 口令保护 ----------

def test_pin_required_flow(make_app):
    app = make_app(pin="1234")
    with app.test_client() as c:
        # 未登录 → 401
        r = c.post("/api/upload", data={"file": (io.BytesIO(_png_bytes()), "a.png")},
                   content_type="multipart/form-data")
        assert r.status_code == 401
        # 错误口令 → 401
        r = c.post("/api/login", json={"pin": "9999"})
        assert r.status_code == 401
        # 正确口令 → 登录后可上传
        r = c.post("/api/login", json={"pin": "1234"})
        assert r.status_code == 200
        r = c.post("/api/upload", data={"file": (io.BytesIO(_png_bytes()), "a.png")},
                   content_type="multipart/form-data")
        assert r.status_code == 200


def test_no_pin_no_login_required(make_app):
    app = make_app()  # 默认无口令
    with app.test_client() as c:
        r = c.post("/api/upload", data={"file": (io.BytesIO(_png_bytes()), "a.png")},
                   content_type="multipart/form-data")
        assert r.status_code == 200


# ---------- 管理端 API（仅本机） ----------

def test_admin_api_loopback_only(make_app):
    app = make_app()
    with app.test_client() as c:
        assert c.get("/api/admin/state").status_code == 200
        assert c.get("/api/admin/state",
                     environ_overrides={"REMOTE_ADDR": "192.168.1.50"}).status_code == 403
        assert c.post("/api/admin/config", json={"config": {"office_name": "X"}},
                      environ_overrides={"REMOTE_ADDR": "192.168.1.50"}).status_code == 403


def test_admin_config_update(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.post("/api/admin/config", json={"config": {"office_name": "新办公室", "max_upload_mb": 8}})
        assert r.status_code == 200
        assert c.get("/api/admin/config").get_json()["config"]["office_name"] == "新办公室"


def test_admin_qr_and_poster(make_app):
    app = make_app()
    with app.test_client() as c:
        qr = c.get("/api/admin/qr?url=http://127.0.0.1:8866/")
        assert qr.status_code == 200
        assert qr.data[:8] == b"\x89PNG\r\n\x1a\n"
        poster = c.get("/api/admin/poster?url=http://127.0.0.1:8866/")
        assert poster.status_code == 200
        assert poster.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_admin_print_test_ok(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.post("/api/admin/print_test")
        assert r.status_code == 200
        assert r.get_json()["printer"] == "Canon MG3000"


def test_admin_log(make_app):
    app = make_app()
    with app.test_client() as c:
        r = c.get("/api/admin/log")
        assert r.status_code == 200
        assert "ok" in r.get_json()
