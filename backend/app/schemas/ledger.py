from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AccountCreate(BaseModel):
    account_code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    label: str | None = Field(default=None, max_length=100)

    @field_validator("account_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper()


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account_code: str
    label: str | None
    created_at: datetime


class TransactionCreate(BaseModel):
    transaction_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    sender_account: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    receiver_account: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="INR", pattern=r"^[A-Za-z]{3}$")
    occurred_at: datetime
    status: Literal["completed", "pending", "failed"] = "completed"

    @field_validator("transaction_id")
    @classmethod
    def reserve_simulator_namespace(cls, value: str) -> str:
        if value.upper().startswith("FGSIM_"):
            raise ValueError("FGSIM_ transaction IDs are reserved for the live simulator")
        return value

    @field_validator("sender_account", "receiver_account", "currency")
    @classmethod
    def uppercase(cls, value: str) -> str:
        return value.upper()

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at needs a timezone offset (e.g. +05:30 or Z)")
        return value

    @model_validator(mode="after")
    def check_accounts(self):
        if self.sender_account == self.receiver_account:
            raise ValueError("Sender and receiver cannot be the same account")
        return self


class TransactionOut(BaseModel):
    id: UUID
    transaction_id: str
    sender_account: str
    receiver_account: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    status: str
    import_batch_id: UUID | None


class ImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    file_name: str
    total_rows: int
    imported_rows: int
    duplicate_rows: int
    created_at: datetime
