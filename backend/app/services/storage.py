"""File storage abstraction.

Development uses LocalDiskStorage under UPLOAD_DIR. Production can switch to
S3Storage by setting STORAGE_DRIVER=s3 and the S3_* env vars. Only metadata /
storage keys are persisted in PostgreSQL.
"""
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import settings


class StorageError(Exception):
    pass


class Storage(Protocol):
    def save(self, stream: BinaryIO, filename: str, content_type: str) -> dict:
        """Persist bytes; returns {key, size_bytes, sha256}."""

    def open(self, key: str) -> BinaryIO: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...


def _ext_of(filename: str) -> str:
    p = Path(filename or "").suffix.lower()
    return p[:16] or ".bin"


class LocalDiskStorage:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base = Path(base_dir or settings.UPLOAD_DIR).resolve()

    def _path(self, key: str) -> Path:
        # keys are generated internally as yyyy/mm/uuid.ext – no traversal risk
        rel = Path(key)
        if ".." in rel.parts or rel.is_absolute():
            raise StorageError("invalid key")
        return self.base / rel

    def save(self, stream: BinaryIO, filename: str, content_type: str) -> dict:
        now = datetime.now(timezone.utc)
        key = f"{now:%Y/%m}/{uuid.uuid4().hex}{_ext_of(filename)}"
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256()
        size = 0
        with dest.open("wb") as out:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                h.update(chunk)
                out.write(chunk)
        return {"key": key, "size_bytes": size, "sha256": h.hexdigest()}

    def open(self, key: str) -> BinaryIO:
        path = self._path(key)
        if not path.is_file():
            raise StorageError("not found")
        return path.open("rb")

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


class S3Storage:
    """S3-compatible object storage driver (boto3 optional dependency)."""

    def __init__(self) -> None:
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise StorageError(
                "STORAGE_DRIVER=s3 requires boto3. Install backend-requirements-s3.txt"
            ) from exc
        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )

    def save(self, stream: BinaryIO, filename: str, content_type: str) -> dict:
        now = datetime.now(timezone.utc)
        key = f"{now:%Y/%m}/{uuid.uuid4().hex}{_ext_of(filename)}"
        h = hashlib.sha256()
        body = b""
        while chunk := stream.read(1024 * 1024):
            body += chunk
            h.update(chunk)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
        return {"key": key, "size_bytes": len(body), "sha256": h.hexdigest()}

    def open(self, key: str) -> BinaryIO:
        import io

        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return io.BytesIO(obj["Body"].read())

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage() if settings.STORAGE_DRIVER == "s3" else LocalDiskStorage()
    return _storage
