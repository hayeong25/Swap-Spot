from abc import ABC, abstractmethod

from app.schemas.rate import RateData


class ExchangeRateSource(ABC):
    source_name: str

    @abstractmethod
    async def fetch_rates(self) -> list[RateData]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...
