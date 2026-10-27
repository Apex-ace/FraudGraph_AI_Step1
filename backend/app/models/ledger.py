"""Financial graph data, isolated by the verified Supabase Auth user ID."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKeyConstraint, Index, Numeric,
    String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    account_code: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("owner_id", "account_code", name="uq_accounts_owner_code"),
        UniqueConstraint("owner_id", "id", name="uq_accounts_owner_id"),
        Index("idx_accounts_owner_created", "owner_id", "created_at"),
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    file_name: Mapped[str] = mapped_column(String(160), nullable=False)
    total_rows: Mapped[int] = mapped_column(nullable=False)
    imported_rows: Mapped[int] = mapped_column(nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint("total_rows >= 0 AND imported_rows >= 0 AND duplicate_rows >= 0", name="ck_import_counts"),
        UniqueConstraint("owner_id", "id", name="uq_import_batches_owner_id"),
        Index("idx_import_batches_owner_created", "owner_id", "created_at"),
    )


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sender_account_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    receiver_account_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    import_batch_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("owner_id", "transaction_id", name="uq_transactions_owner_ref"),
        CheckConstraint("amount > 0", name="ck_transactions_positive_amount"),
        CheckConstraint("sender_account_id <> receiver_account_id", name="ck_transactions_distinct_accounts"),
        CheckConstraint("status IN ('completed','pending','failed')", name="ck_transactions_status"),
        ForeignKeyConstraint(["owner_id", "sender_account_id"], ["accounts.owner_id", "accounts.id"], name="fk_transactions_sender"),
        ForeignKeyConstraint(["owner_id", "receiver_account_id"], ["accounts.owner_id", "accounts.id"], name="fk_transactions_receiver"),
        ForeignKeyConstraint(["owner_id", "import_batch_id"], ["import_batches.owner_id", "import_batches.id"], name="fk_transactions_batch"),
        Index("idx_transactions_owner_occurred", "owner_id", "occurred_at"),
        Index("idx_transactions_sender", "owner_id", "sender_account_id"),
        Index("idx_transactions_receiver", "owner_id", "receiver_account_id"),
    )
