"""Upload validation: type sniffing, size caps and storage hand-off."""
import hashlib
from typing import BinaryIO

from app.ai.image_analysis import load_image
from app.core.config import settings
from app.services.storage import get_storage

IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
VIDEO_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
AUDIO_TYPES = {"audio/webm": ".webm", "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/ogg": ".ogg"}

MAX_BYTES = {
    "image": settings.MAX_IMAGE_MB * 1024 * 1024,
    "video": settings.MAX_VIDEO_MB * 1024 * 1024,
    "audio": settings.MAX_AUDIO_MB * 1024 * 1024,
}


class UploadRejected(Exception):
    pass


def detect_kind(filename: str, content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ct in IMAGE_TYPES or ext in ("jpg", "jpeg", "png", "webp"):
        return "image"
    if ct in VIDEO_TYPES or ext in ("mp4", "webm", "mov"):
        return "video"
    if ct in AUDIO_TYPES or ext in ("webm", "mp3", "m4a", "wav", "ogg"):
        # webm is ambiguous (audio/video); caller may override after sniffing
        return "audio"
    raise UploadRejected(f"unsupported file type: {filename}")


def validate_image(data: bytes) -> tuple[int, int]:
    try:
        img = load_image(data)
        if img.width < 32 or img.height < 32:
            raise UploadRejected("image too small")
        return img.width, img.height
    except UploadRejected:
        raise
    except Exception as exc:
        raise UploadRejected("corrupted or unsupported image") from exc


def store_upload(
    stream: BinaryIO,
    filename: str,
    content_type: str,
    max_kind_override: str | None = None,
) -> dict:
    """Validate + persist one upload. Returns metadata dict for ReportMedia."""
    kind = max_kind_override or detect_kind(filename, content_type)
    allowed = {"image": IMAGE_TYPES, "video": VIDEO_TYPES, "audio": AUDIO_TYPES}[kind]
    ct = (content_type or "").split(";")[0].strip().lower()

    head = stream.read(12)
    stream.seek(0)
    if len(head) == 0:
        raise UploadRejected("empty file")

    data_hash = hashlib.sha256()
    total = 0
    chunks = []
    cap = MAX_BYTES[kind]
    while chunk := stream.read(1024 * 512):
        total += len(chunk)
        if total > cap:
            raise UploadRejected(f"file exceeds {kind} limit of {settings.__get__(f'MAX_{kind.upper()}_MB')} MB")
        data_hash.update(chunk)
        chunks.append(chunk)

    if kind == "image" and ct not in allowed:
        # trust magic bytes via PIL instead of client mime
        blob = b"".join(chunks)
        w, h = validate_image(blob)
    else:
        if ct not in allowed:
            raise UploadRejected(f"mime {ct} not allowed for {kind}")
        w = h = None

    meta = get_storage().save(_BytesReader(chunks), filename, content_type)
    return {
        "kind": kind,
        "storage_key": meta["key"],
        "mime_type": ct or "application/octet-stream",
        "size_bytes": meta["size_bytes"],
        "sha256": meta["sha256"],
        "width": w,
        "height": h,
    }


class _BytesReader:
    """Tiny seekable reader over buffered chunks."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._buf = b"".join(chunks)
        self._pos = 0

    def read(self, n: int = -1) -> bytes:
        if n == -1:
            out = self._buf[self._pos:]
            self._pos = len(self._buf)
            return out
        out = self._buf[self._pos : self._pos + n]
        self._pos += len(out)
        return out

    def seek(self, pos: int, whence: int = 0) -> int:
        self._pos = pos
        return self._pos
