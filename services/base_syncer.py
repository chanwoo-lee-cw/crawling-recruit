from abc import ABC, abstractmethod

from services.jobs.job_service import JobService


class BaseSyncer(ABC):
    def __init__(self, service: JobService):
        self.service = service

    @abstractmethod
    def sync(self, **kwargs) -> str:
        ...
