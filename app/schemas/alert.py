from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class AlertCreate(BaseModel):
    currency_code: str
    condition: Literal["below", "above", "percent_change"]
    threshold: float

    @field_validator("threshold")
    @classmethod
    def threshold_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("threshold must be positive")
        return v

    @field_validator("currency_code")
    @classmethod
    def currency_code_uppercase(cls, v: str) -> str:
        return v.strip().upper()


class AlertResponse(BaseModel):
    id: int
    currency_code: str
    condition: str
    threshold: float
    is_active: bool
    last_triggered_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
