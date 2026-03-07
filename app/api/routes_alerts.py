from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.models.alert import Alert
from app.models.database import async_session
from app.schemas.alert import AlertCreate, AlertResponse

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/")
async def list_alerts() -> list[AlertResponse]:
    async with async_session() as session:
        result = await session.execute(select(Alert).where(Alert.is_active.is_(True)))
        alerts = result.scalars().all()
        return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/")
async def create_alert(data: AlertCreate) -> AlertResponse:
    async with async_session() as session:
        alert = Alert(
            currency_code=data.currency_code.upper(),
            condition=data.condition,
            threshold=data.threshold,
        )
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        return AlertResponse.model_validate(alert)


@router.delete("/{alert_id}")
async def delete_alert(alert_id: int) -> dict:
    async with async_session() as session:
        result = await session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.is_active.is_(True))
        )
        alert = result.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.is_active = False
        await session.commit()
        return {"ok": True}
