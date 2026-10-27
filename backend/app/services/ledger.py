"""Step 2 account and transaction persistence, with strict per-user ownership."""
import csv
import io
from datetime import timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ledger import Account, ImportBatch, Transaction
from app.schemas.ledger import AccountCreate, TransactionCreate

MAX_IMPORT_ROWS = 1000
MAX_IMPORT_BYTES = 2 * 1024 * 1024
CSV_FIELDS = ["transaction_id", "sender_account", "receiver_account", "amount", "currency", "occurred_at", "status"]


def get_owner(user: dict) -> UUID:
    return UUID(user["id"])


def get_accounts(db: Session, owner: UUID, limit: int = 100):
    return db.scalars(
        select(Account).where(Account.owner_id == owner).order_by(Account.created_at.desc(), Account.account_code).limit(limit)
    ).all()


def create_account(db: Session, owner: UUID, value: AccountCreate):
    if db.scalar(select(Account.id).where(Account.owner_id == owner, Account.account_code == value.account_code)):
        raise HTTPException(409, detail="Account code already exists")
    account = Account(owner_id=owner, account_code=value.account_code, label=value.label)
    db.add(account)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="Account code already exists") from exc
    db.refresh(account)
    return account


def serialize_transaction(t: Transaction, codes: dict[UUID, str]):
    return {
        "id": t.id,
        "transaction_id": t.transaction_id,
        "sender_account": codes[t.sender_account_id],
        "receiver_account": codes[t.receiver_account_id],
        "amount": t.amount,
        "currency": t.currency,
        "occurred_at": t.occurred_at,
        "status": t.status,
        "import_batch_id": t.import_batch_id,
    }


def list_transactions(db: Session, owner: UUID, limit: int, offset: int, status: str | None):
    stmt = select(Transaction).where(Transaction.owner_id == owner)
    if status:
        stmt = stmt.where(Transaction.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    transactions = db.scalars(stmt.order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).offset(offset).limit(limit)).all()
    account_ids = {t.sender_account_id for t in transactions} | {t.receiver_account_id for t in transactions}
    codes = {}
    if account_ids:
        codes = {a.id: a.account_code for a in db.scalars(select(Account).where(Account.owner_id == owner, Account.id.in_(account_ids))).all()}
    return {"items": [serialize_transaction(t, codes) for t in transactions], "total": total, "limit": limit, "offset": offset}


def create_transaction(db: Session, owner: UUID, value: TransactionCreate):
    accounts = db.scalars(select(Account).where(Account.owner_id == owner, Account.account_code.in_([value.sender_account, value.receiver_account]))).all()
    codes = {account.account_code: account for account in accounts}
    missing = [code for code in (value.sender_account, value.receiver_account) if code not in codes]
    if missing:
        raise HTTPException(422, detail=f"Create account(s) first: {', '.join(missing)}")
    if db.scalar(select(Transaction.id).where(Transaction.owner_id == owner, Transaction.transaction_id == value.transaction_id)):
        raise HTTPException(409, detail="Transaction ID already exists")
    t = Transaction(
        owner_id=owner, transaction_id=value.transaction_id,
        sender_account_id=codes[value.sender_account].id, receiver_account_id=codes[value.receiver_account].id,
        amount=value.amount, currency=value.currency, occurred_at=value.occurred_at.astimezone(timezone.utc), status=value.status,
    )
    db.add(t)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="Transaction ID already exists or violates a database constraint") from exc
    db.refresh(t)
    return serialize_transaction(t, {a.id: a.account_code for a in accounts})


def parse_csv(content: bytes):
    if not content:
        raise HTTPException(422, detail="CSV is empty")
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(413, detail="CSV exceeds 2 MB")
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames or []
        if any(header is None for header in headers) or len(set(headers)) != len(headers):
            raise HTTPException(422, detail="CSV has invalid or duplicate column names")
        missing = [name for name in CSV_FIELDS if name not in headers]
        if missing:
            raise HTTPException(422, detail=f"Missing CSV columns: {', '.join(missing)}")
        rows = []
        errors = []
        seen = {}
        duplicates_within_file = 0
        for line_number, row in enumerate(reader, start=2):
            if line_number > MAX_IMPORT_ROWS + 1:
                raise HTTPException(413, detail="Maximum 1000 data rows per CSV")
            try:
                if None in row or any(row.get(key) is None for key in CSV_FIELDS):
                    raise ValueError("Row contains missing or extra columns")
                clean = {key: (row.get(key) or "").strip() for key in CSV_FIELDS}
                transaction = TransactionCreate.model_validate(clean)
                ref = transaction.transaction_id
                if ref in seen:
                    if seen[ref] == transaction:
                        duplicates_within_file += 1
                        continue
                    raise ValueError(f"Conflicting repeated transaction_id '{ref}'")
                seen[ref] = transaction
                rows.append(transaction)
            except (ValidationError, ValueError) as exc:
                errors.append({"row": line_number, "error": str(exc).splitlines()[0][:200]})
                if len(errors) == 15:
                    break
    except (UnicodeDecodeError, csv.Error) as exc:
        raise HTTPException(422, detail="Invalid CSV file or text encoding; use UTF-8") from exc
    if errors:
        raise HTTPException(422, detail={"message": "CSV validation failed. No rows were imported.", "errors": errors})
    if not rows:
        raise HTTPException(422, detail="No valid transaction rows")
    return rows, len(rows) + duplicates_within_file, duplicates_within_file


def import_transactions(db: Session, owner: UUID, filename: str, parsed):
    rows, total_rows, file_duplicates = parsed
    refs = [row.transaction_id for row in rows]
    existing = {t.transaction_id: t for t in db.scalars(select(Transaction).where(Transaction.owner_id == owner, Transaction.transaction_id.in_(refs))).all()}
    needed_codes = {row.sender_account for row in rows} | {row.receiver_account for row in rows}
    accounts = {a.account_code: a for a in db.scalars(select(Account).where(Account.owner_id == owner, Account.account_code.in_(needed_codes))).all()}

    # Reusing the same transaction ID with different values is rejected rather than silently ignored.
    for row in rows:
        original = existing.get(row.transaction_id)
        if original:
            sender = accounts.get(row.sender_account)
            receiver = accounts.get(row.receiver_account)
            # Existing transactions always reference valid owner-scoped accounts.
            if not sender or not receiver:
                raise HTTPException(409, detail=f"Transaction ID {row.transaction_id} already exists with different account(s)")
            if (original.sender_account_id != sender.id or original.receiver_account_id != receiver.id or
                original.amount != row.amount or original.currency != row.currency or original.status != row.status or
                (original.occurred_at.replace(tzinfo=timezone.utc) if original.occurred_at.tzinfo is None else original.occurred_at.astimezone(timezone.utc)) != row.occurred_at.astimezone(timezone.utc)):
                raise HTTPException(409, detail=f"Transaction ID {row.transaction_id} already exists with different data")
    batch = ImportBatch(owner_id=owner, file_name=filename[:160], total_rows=total_rows,
                        imported_rows=len(rows) - len(existing), duplicate_rows=file_duplicates + len(existing))
    try:
        db.add(batch)
        db.flush()
        for code in sorted(needed_codes):
            if code not in accounts:
                a = Account(owner_id=owner, account_code=code, label="Auto-created by CSV import")
                db.add(a)
                db.flush()
                accounts[code] = a
        for row in rows:
            if row.transaction_id in existing:
                continue
            db.add(Transaction(
                owner_id=owner, transaction_id=row.transaction_id,
                sender_account_id=accounts[row.sender_account].id,
                receiver_account_id=accounts[row.receiver_account].id,
                amount=row.amount, currency=row.currency, occurred_at=row.occurred_at.astimezone(timezone.utc),
                status=row.status, import_batch_id=batch.id,
            ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="Import conflicts with another transaction or a database constraint") from exc
    db.refresh(batch)
    return batch


def list_import_batches(db: Session, owner: UUID, limit: int = 25):
    return db.scalars(select(ImportBatch).where(ImportBatch.owner_id == owner).order_by(ImportBatch.created_at.desc()).limit(limit)).all()


def overview(db: Session, owner: UUID):
    return {
        "accounts": db.scalar(select(func.count()).select_from(Account).where(Account.owner_id == owner)) or 0,
        "transactions": db.scalar(select(func.count()).select_from(Transaction).where(Transaction.owner_id == owner)) or 0,
        "completed_transactions": db.scalar(select(func.count()).select_from(Transaction).where(Transaction.owner_id == owner, Transaction.status == "completed")) or 0,
        "import_batches": db.scalar(select(func.count()).select_from(ImportBatch).where(ImportBatch.owner_id == owner)) or 0,
    }
