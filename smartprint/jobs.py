# -*- coding: utf-8 -*-
"""SmartPrint 打印任务管理：上传登记、队列、后台打印、状态查询、定时清理"""
import queue
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from . import config, converters, printer
from .logger import get_logger

log = get_logger()

STATUS_UPLOADED = "uploaded"   # 已上传，等待打印
STATUS_QUEUED = "queued"       # 已提交打印，排队中
STATUS_PRINTING = "printing"   # 打印中
STATUS_DONE = "done"           # 完成
STATUS_FAILED = "failed"       # 失败


class JobManager:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._jobs = {}          # id -> job dict
        self._lock = threading.Lock()
        self._queue = queue.Queue()  # (job_id, settings)
        self._worker = None

    # ---------- 任务登记 ----------

    def add_upload(self, saved_path: Path, name: str, size: int) -> dict:
        jid = uuid.uuid4().hex[:12]
        job = {
            "id": jid,
            "name": name,
            "path": str(saved_path),
            "size": size,
            "status": STATUS_UPLOADED,
            "error": "",
            "pages": 0,
            "printer": "",
            "settings": None,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished": "",
        }
        with self._lock:
            self._jobs[jid] = job
        log.info(f"[job:{jid}] 上传文件：{name}（{size} 字节）")
        return job

    def remove(self, jid: str):
        with self._lock:
            job = self._jobs.get(jid)
            if job and job["status"] not in (STATUS_QUEUED, STATUS_PRINTING):
                del self._jobs[jid]
                return True
        return False

    def get(self, jid: str):
        with self._lock:
            return dict(self._jobs[jid]) if jid in self._jobs else None

    def list_all(self):
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j["created"], reverse=True)
        return jobs

    def _set(self, jid: str, **kw):
        with self._lock:
            if jid in self._jobs:
                self._jobs[jid].update(kw)

    # ---------- 打印 ----------

    def enqueue(self, jid: str, settings: dict):
        with self._lock:
            job = self._jobs.get(jid)
            if not job:
                return False
            if job["status"] == STATUS_PRINTING:
                return False
            job["status"] = STATUS_QUEUED
            job["settings"] = settings
            self._queue.put((jid, settings))
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._run, daemon=True, name="print-worker")
            self._worker.start()
        return True

    def _run(self):
        while True:
            try:
                jid, settings = self._queue.get(timeout=2)
            except queue.Empty:
                if not self._queue.empty():
                    continue
                return
            self._print_one(jid, settings)

    def _print_one(self, jid: str, settings: dict):
        with self._lock:
            job = self._jobs.get(jid)
            if not job:
                return
            name = job["name"]
            path = Path(job["path"])
        log.info(f"[job:{jid}] 开始打印：{name}")
        try:
            pname = printer.resolve_printer(self.cfg.get("printer", ""))
            tmp_dir = Path(self.cfg.get("_tmp_dir") or str(config.TMP_DIR))
            pdf_path = converters.ensure_pdf(path, tmp_dir)
            printer.print_pdf(str(pdf_path), pname, settings)
            self._set(jid, status=STATUS_DONE, printer=pname,
                      finished=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            log.info(f"[job:{jid}] 打印完成：{name}（打印机：{pname}）")
        except Exception as e:
            self._set(jid, status=STATUS_FAILED, error=str(e),
                      finished=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            log.error(f"[job:{jid}] 打印失败：{name}：{e}")

    # ---------- 清理 ----------

    def cleanup(self):
        """删除过期上传文件与对应的失败/完成记录"""
        days = int(self.cfg.get("clean_days", 7))
        cutoff = time.time() - days * 86400
        removed = []
        with self._lock:
            for jid, job in list(self._jobs.items()):
                try:
                    if Path(job["path"]).stat().st_mtime < cutoff:
                        if job["status"] in (STATUS_DONE, STATUS_FAILED, STATUS_UPLOADED):
                            removed.append(job["path"])
                            del self._jobs[jid]
                except OSError:
                    continue
        for p in removed:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass
        if removed:
            log.info(f"清理过期文件 {len(removed)} 个")

    def start_cleaner(self):
        def loop():
            while True:
                time.sleep(3600)
                try:
                    self.cleanup()
                except Exception as e:
                    log.error(f"清理任务异常：{e}")
        threading.Thread(target=loop, daemon=True, name="cleaner").start()
