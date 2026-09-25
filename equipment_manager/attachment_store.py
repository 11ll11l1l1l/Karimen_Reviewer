from __future__ import annotations

import mimetypes
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path


def _safe_segment(value: str) -> str:
    raw=(value or "").strip()
    return "".join(ch if ch.isalnum() or ch in {"-","_","."} else "_" for ch in raw)[:120] or "unknown"


def entity_attachment_dir(root: str, entity_type: str, entity_key: str) -> Path:
    folder=Path(root)/"Attachments"/_safe_segment(entity_type.upper())/_safe_segment(str(entity_key))
    folder.mkdir(parents=True,exist_ok=True)
    return folder


def _atomic_copy(src: Path, dst: Path) -> None:
    temp=dst.with_name(f".{dst.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(src,temp)
        os.replace(temp,dst)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def store_attachment_file(source_path: str, root: str, entity_type: str, entity_key: str) -> dict:
    src=Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(source_path)
    folder=entity_attachment_dir(root,entity_type,entity_key)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dst=folder/f"{stamp}_{_safe_segment(src.name)}"
    _atomic_copy(src,dst)
    media_type=mimetypes.guess_type(src.name)[0] or "application/octet-stream"
    return {
        "stored_path":str(dst),
        "original_name":src.name,
        "media_type":media_type,
    }


def store_clipboard_image(image, root: str, entity_type: str, entity_key: str) -> dict:
    folder=entity_attachment_dir(root,entity_type,entity_key)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dst=folder/f"{stamp}_screenshot.png"
    temp=dst.with_name(f".{dst.name}.{uuid.uuid4().hex}.tmp")
    try:
        if not image.save(str(temp),"PNG"):
            raise IOError("Could not save clipboard image")
        os.replace(temp,dst)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    return {
        "stored_path":str(dst),
        "original_name":"screenshot.png",
        "media_type":"image/png",
    }


def duplicate_attachment_file(source_path: str, root: str, entity_type: str, entity_key: str) -> dict:
    return store_attachment_file(source_path,root,entity_type,entity_key)
