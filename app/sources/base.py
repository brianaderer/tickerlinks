from abc import ABC, abstractmethod


class BaseFetcher(ABC):
    @abstractmethod
    def fetch(self, **kwargs) -> list[dict]:
        """Pull raw data and return normalized dicts ready for DB insertion."""
        ...
