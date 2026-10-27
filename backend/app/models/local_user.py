"""Local demo identities; separate from financial account records."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Uuid, func
from app.models.types import UTCDateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.ledger import Base


class LocalUser(Base):
    __tablename__ = "local_users"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(timezone.utc),
        server_default=func.now(), nullable=False,
    )
