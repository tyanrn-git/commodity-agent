from abc import ABC, abstractmethod


class ObjectStorage(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> str:
        """Save bytes and return storage key."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Read bytes by storage key."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists."""
