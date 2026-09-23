from __future__ import annotations

import json
import logging
import os
import socket
import sys
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload={
            "timestamp":datetime.now(timezone.utc).isoformat(),
            "level":record.levelname,
            "logger":record.name,
            "message":record.getMessage(),
            "process":record.process,
            "thread":record.threadName,
            "workstation":socket.gethostname(),
        }
        if record.exc_info:
            payload["exception"]="".join(traceback.format_exception(*record.exc_info))
        for key in ("event","entity_type","entity_key","username","app_version"):
            if hasattr(record,key):payload[key]=getattr(record,key)
        return json.dumps(payload,ensure_ascii=False,sort_keys=True)


def configure_logging(app_name: str = "ems") -> Path:
    root=Path(os.getenv("EMS_LOG_ROOT",str(Path.cwd()/"equipment_logs"))).expanduser().resolve()
    root.mkdir(parents=True,exist_ok=True)
    path=root/f"{app_name}.jsonl"
    logger=logging.getLogger()
    logger.setLevel(os.getenv("EMS_LOG_LEVEL","INFO").upper())
    if not any(isinstance(h,RotatingFileHandler) and getattr(h,"baseFilename","")==str(path) for h in logger.handlers):
        handler=RotatingFileHandler(path,maxBytes=10*1024*1024,backupCount=10,encoding="utf-8")
        handler.setFormatter(JsonLineFormatter())
        logger.addHandler(handler)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger(__name__).info("Application logging initialized",extra={"event":"app.logging.ready"})
    return path


def install_exception_hook(app_name: str = "ems"):
    previous=sys.excepthook
    def hook(exc_type,exc_value,exc_tb):
        logging.getLogger(app_name).critical(
            "Uncaught application exception",
            exc_info=(exc_type,exc_value,exc_tb),
            extra={"event":"app.uncaught_exception"},
        )
        previous(exc_type,exc_value,exc_tb)
    sys.excepthook=hook
