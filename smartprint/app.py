# -*- coding: utf-8 -*-
"""SmartPrint Web 服务：手机端页面 + 上传/打印 API + 本地管理页"""
import re
import uuid
from pathlib import Path

from flask import (
    Flask, Response, jsonify, request, send_file, session
)

from . import autostart, config, qr, tunnel
from .jobs import JobManager
from .logger import get_logger

log = get_logger()

WEB_DIR = Path(__file__).resolve().parent / "web"

_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_name(name: str) -> str:
    # 手动切分路径：把 \ 统一成 / 再取最后一段，
    # 保证 Windows / Linux 对反斜杠分隔符的处理一致（跨平台测试通过）
    name = (name or "file").replace("\\", "/").rsplit("/", 1)[-1]
    name = _INVALID_NAME.sub("_", name).strip(" .")
    return name or "file"


def _loopback() -> bool:
    ip = request.remote_addr or ""
    return ip.startswith("127.") or ip == "::1" or ip == "localhost"


def create_app(cfg: dict) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.secret_key = cfg.get("_secret", uuid.uuid4().hex)
    cfg["_tmp_dir"] = str(config.TMP_DIR)
    config.ensure_dirs()

    jobs = JobManager(cfg)
    jobs.start_cleaner()
    tunnel_mgr = tunnel.TunnelManager(cfg)

    # 清理超过 1 天的转换临时文件
    try:
        import time as _time
        _cut = _time.time() - 86400
        for f in config.TMP_DIR.glob("*"):
            try:
                if f.stat().st_mtime < _cut:
                    f.unlink(missing_ok=True)
            except OSError:
                pass
    except Exception:
        pass

    # ---------- 工具 ----------

    def public_config() -> dict:
        return {
            "office_name": cfg.get("office_name", "扫码打印"),
            "pin_required": bool(cfg.get("pin", "")),
            "printers": _printers(),
            "default_printer": cfg.get("printer", ""),
            "print_defaults": cfg.get("print_defaults", {}),
            "max_upload_mb": cfg.get("max_upload_mb", 50),
            "access_mode": cfg.get("access_mode", "lan"),
            "tunnel": tunnel_mgr.state(),
        }

    def _printers():
        try:
            from . import printer
            return printer.list_printers()
        except Exception:
            return []

    def check_auth():
        if not cfg.get("pin", ""):
            return True
        return session.get("authed") is True

    def require_auth():
        if not check_auth():
            return jsonify({"ok": False, "error": "需要口令", "code": "need_auth"}), 401
        return None

    def require_admin():
        if not _loopback():
            return jsonify({"ok": False, "error": "管理页仅限本机访问"}), 403
        return None

    def current_url() -> str:
        return tunnel_mgr.get_public_url() or (tunnel_mgr.lan_urls or [""])[0]

    # ---------- 页面 ----------

    @app.get("/")
    def index():
        return send_file(WEB_DIR / "index.html", mimetype="text/html")

    @app.get("/admin")
    def admin():
        if not _loopback():
            return "管理页仅限本机访问（请在本机打开 http://127.0.0.1:8866/admin）", 403
        return send_file(WEB_DIR / "admin.html", mimetype="text/html")

    @app.get("/favicon.ico")
    def favicon():
        return Response(status=204)

    # ---------- 手机端 API ----------

    @app.get("/api/config")
    def api_config():
        return jsonify({"ok": True, **public_config()})

    @app.post("/api/login")
    def api_login():
        pin = (request.json or {}).get("pin", "")
        if cfg.get("pin", "") and pin != cfg.get("pin"):
            return jsonify({"ok": False, "error": "口令错误"}), 401
        session["authed"] = True
        return jsonify({"ok": True})

    @app.post("/api/upload")
    def api_upload():
        err = require_auth()
        if err:
            return err
        files = request.files.getlist("file")
        if not files:
            return jsonify({"ok": False, "error": "未选择文件"}), 400
        if "uid" not in session:
            session["uid"] = uuid.uuid4().hex[:8]
        uid = session["uid"]
        created = []
        for f in files:
            if not f or not f.filename:
                continue
            name = _safe_name(f.filename)
            jid = uuid.uuid4().hex[:12]
            dest = config.UPLOAD_DIR / f"{jid}_{name}"
            f.save(str(dest))
            job = jobs.add_upload(dest, name, dest.stat().st_size)
            job["uid"] = uid
            created.append(job)
        return jsonify({"ok": True, "jobs": created})

    @app.post("/api/print")
    def api_print():
        err = require_auth()
        if err:
            return err
        data = request.json or {}
        job_ids = data.get("job_ids") or []
        if not job_ids:
            return jsonify({"ok": False, "error": "没有要打印的文件"}), 400
        settings = dict(cfg.get("print_defaults", {}))
        s = data.get("settings") or {}
        for k in ("color", "duplex", "orientation", "fit", "pages"):
            if k in s and s[k] is not None and s[k] != "":
                settings[k] = s[k]
        try:
            settings["copies"] = max(1, min(99, int(s.get("copies", settings.get("copies", 1)))))
        except Exception:
            pass
        ok_ids = []
        for jid in job_ids:
            if jobs.enqueue(jid, settings):
                ok_ids.append(jid)
        return jsonify({"ok": True, "job_ids": ok_ids, "settings": settings})

    @app.get("/api/jobs")
    def api_jobs():
        # 本机管理端看全部；手机端只看自己上传的任务
        if _loopback():
            return jsonify({"ok": True, "jobs": jobs.list_all()})
        uid = session.get("uid")
        mine = [j for j in jobs.list_all() if j.get("uid") == uid]
        return jsonify({"ok": True, "jobs": mine})

    @app.get("/api/job/<jid>")
    def api_job(jid):
        job = jobs.get(jid)
        if not job:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        return jsonify({"ok": True, "job": job})

    @app.delete("/api/job/<jid>")
    def api_job_delete(jid):
        if jobs.remove(jid):
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "打印中或不存在，无法删除"}), 400

    # ---------- 管理端 API（仅本机） ----------

    @app.get("/api/admin/state")
    def admin_state():
        if require_admin():
            return require_admin()
        return jsonify({"ok": True, "state": tunnel_mgr.state(), "jobs": jobs.list_all()})

    @app.get("/api/admin/config")
    def admin_get_config():
        if require_admin():
            return require_admin()
        return jsonify({"ok": True, "config": cfg})

    @app.post("/api/admin/config")
    def admin_set_config():
        err = require_admin()
        if err:
            return err
        data = (request.json or {}).get("config") or {}
        allowed = {
            "host", "port", "printer", "office_name", "max_upload_mb", "pin",
            "access_mode", "cloudflare", "frp", "custom_url", "autostart",
            "clean_days", "print_defaults",
        }
        changed = False
        for k, v in data.items():
            if k in allowed:
                cfg[k] = v
                changed = True
        try:
            cfg["port"] = int(cfg.get("port", 8866))
        except Exception:
            cfg["port"] = 8866
        try:
            cfg["max_upload_mb"] = int(cfg.get("max_upload_mb", 50))
        except Exception:
            cfg["max_upload_mb"] = 50
        app.config["MAX_CONTENT_LENGTH"] = cfg["max_upload_mb"] * 1024 * 1024
        config.save(cfg)
        autostart.apply(cfg)
        if changed:
            log.info("配置已更新")
        return jsonify({"ok": True, "note": "配置已保存（端口等改动需重启应用生效）"})

    @app.get("/api/admin/qr")
    def admin_qr():
        err = require_admin()
        if err:
            return err
        url = request.args.get("url") or current_url()
        if not url:
            return jsonify({"ok": False, "error": "暂无可用访问地址"}), 400
        png = qr.qr_bytes(url)
        return Response(png, mimetype="image/png")

    @app.get("/api/admin/poster")
    def admin_poster():
        err = require_admin()
        if err:
            return err
        url = request.args.get("url") or current_url()
        if not url:
            return jsonify({"ok": False, "error": "暂无可用访问地址"}), 400
        png = qr.build_poster(url, cfg.get("office_name", "扫码打印"))
        return Response(png, mimetype="image/png")

    @app.post("/api/admin/print_poster")
    def admin_print_poster():
        err = require_admin()
        if err:
            return err
        url = request.args.get("url") or current_url()
        if not url:
            return jsonify({"ok": False, "error": "暂无可用访问地址"}), 400
        try:
            from . import printer
            pname = printer.resolve_printer(cfg.get("printer", ""))
            settings = dict(cfg.get("print_defaults", {}))
            qr.print_poster(url, cfg.get("office_name", "扫码打印"), pname, settings)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/api/admin/print_test")
    def admin_print_test():
        err = require_admin()
        if err:
            return err
        try:
            from . import printer
            pname = printer.resolve_printer(cfg.get("printer", ""))
            printer.print_test_page(pname, dict(cfg.get("print_defaults", {})))
            return jsonify({"ok": True, "printer": pname})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/api/admin/restart_tunnel")
    def admin_restart_tunnel():
        err = require_admin()
        if err:
            return err
        threading_restart(tunnel_mgr)
        return jsonify({"ok": True})

    @app.get("/api/admin/log")
    def admin_log():
        err = require_admin()
        if err:
            return err
        return jsonify({"ok": True, "log": _tail_log()})

    # 上传大小限制
    app.config["MAX_CONTENT_LENGTH"] = cfg.get("max_upload_mb", 50) * 1024 * 1024

    return app


def _tail_log():
    from . import logger
    return logger.tail(300)


def threading_restart(tunnel_mgr):
    import threading
    threading.Thread(target=tunnel_mgr.restart, daemon=True).start()
