"""Persisted behavioral detections. Never label an allegation as confirmed fraud."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, Index, JSON, String, Uuid, UniqueConstraint, func
from app.models.types import UTCDateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.ledger import Base


class FraudAlert(Base):
    __tablename__ = 'fraud_alerts'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(24), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_index: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(String(240), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='open')
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint('owner_id', 'fingerprint', name='uq_fraud_alert_owner_fingerprint'),
                      Index('idx_fraud_alert_owner_created', 'owner_id', 'created_at'))
