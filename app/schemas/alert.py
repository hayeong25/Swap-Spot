from datetime import datetime

from pydantic import BaseModel


class AlertCreate(BaseModel):
    currency_code: str
    condition: str  # below, above, percent_change
    threshold: float


class AlertResponse(BaseModel):
    id: int
    currency_code: str
    condition: str
    threshold: float
    is_active: bool
    last_triggered_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
