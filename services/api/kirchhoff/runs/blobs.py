import threading
from datetime import timedelta
from typing import Protocol

BUCKET = "ordinal-mep.firebasestorage.app"


class SigningUnavailable(NotImplementedError):
    """Raised by a BlobStore that cannot produce a signed URL (e.g. in-process MemoryBlobStore with no
    public_base). /api/files catches exactly this type and serves the bytes inline instead."""


class BlobStore(Protocol):
    def put(self, path: str, data: bytes, content_type: str) -> str: ...
    def get(self, path: str) -> bytes: ...
    def exists(self, path: str) -> bool: ...
    def delete_prefix(self, prefix: str) -> int: ...
    def signed_url(self, path: str, ttl_s: int = 600) -> str: ...


class MemoryBlobStore:
    """In-process blobs. `public_base=None` means URLs cannot be signed (local development): /api/files then
    serves the bytes inline instead of a signed URL."""

    def __init__(self, public_base: str | None = "https://storage.example.test") -> None:
        self.blobs: dict[str, tuple[bytes, str]] = {}
        self.public_base = public_base
        self._lock = threading.Lock()

    def put(self, path: str, data: bytes, content_type: str) -> str:
        with self._lock:
            self.blobs[path] = (bytes(data), content_type)
        return path

    def get(self, path: str) -> bytes:
        with self._lock:
            return self.blobs[path][0]

    def exists(self, path: str) -> bool:
        with self._lock:
            return path in self.blobs

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [k for k in self.blobs if k.startswith(prefix)]
            for k in keys:
                del self.blobs[k]
            return len(keys)

    def signed_url(self, path: str, ttl_s: int = 600) -> str:
        if not self.exists(path):
            raise KeyError(path)
        if self.public_base is None:
            raise SigningUnavailable("memory blobs cannot be signed")
        return f"{self.public_base}/{path}?ttl={ttl_s}"


class GcsBlobStore:
    def __init__(self, bucket: str = BUCKET) -> None:
        self._name = bucket
        self._bucket = None
        self._lock = threading.Lock()

    def _b(self):
        with self._lock:
            if self._bucket is None:
                from google.cloud import storage
                self._bucket = storage.Client(project="ordinal-mep").bucket(self._name)
            return self._bucket

    def put(self, path: str, data: bytes, content_type: str) -> str:
        self._b().blob(path).upload_from_string(data, content_type=content_type)
        return path

    def get(self, path: str) -> bytes:
        return self._b().blob(path).download_as_bytes()

    def exists(self, path: str) -> bool:
        return self._b().blob(path).exists()

    def delete_prefix(self, prefix: str) -> int:
        n = 0
        for b in self._b().client.list_blobs(self._name, prefix=prefix):
            b.delete()
            n += 1
        return n

    def signed_url(self, path: str, ttl_s: int = 600) -> str:
        import google.auth
        from google.auth.transport.requests import Request

        creds, _ = google.auth.default()
        creds.refresh(Request())
        kw = {}
        if getattr(creds, "service_account_email", None):  # Cloud Run: sign through IAM signBlob
            kw = {"service_account_email": creds.service_account_email, "access_token": creds.token}
        return self._b().blob(path).generate_signed_url(version="v4", expiration=timedelta(seconds=ttl_s),
                                                        method="GET", **kw)
