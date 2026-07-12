from pathlib import Path

from app.config import settings
from app.integrations.storage.base import ObjectStorage


class LocalFilesystemStorage(ObjectStorage):
    def __init__(self, base_path: str | None = None) -> None:
        self.base_path = Path(base_path or settings.storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _full_path(self, key: str) -> Path:
        path = self.base_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, key: str, data: bytes) -> str:
        path = self._full_path(key)
        path.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        return self._full_path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._full_path(key).exists()
