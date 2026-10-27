"""Run: python -m pytest -q tests/test_ledger.py (from backend; needs pytest)."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.ledger import Account, Base, ImportBatch, Transaction
from app.schemas.ledger import AccountCreate, TransactionCreate
from app.services.ledger import (
    create_account, create_transaction, get_accounts, import_transactions,
    list_transactions, overview, parse_csv,
)


@pytest.fixture
def session():
    engine = create_engine('sqlite+pysqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    @event.listens_for(engine, 'connect')
    def fks(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_accounts_isolated_per_verified_owner(session):
    first, second = uuid4(), uuid4()
    create_account(session, first, AccountCreate(account_code='acc001'))
    assert [a.account_code for a in get_accounts(session, first)] == ['ACC001']
    assert get_accounts(session, second) == []
    create_account(session, second, AccountCreate(account_code='acc001'))
    assert overview(session, first)['accounts'] == 1
    assert overview(session, second)['accounts'] == 1
    with pytest.raises(HTTPException) as error:
        create_account(session, first, AccountCreate(account_code='acc001'))
    assert error.value.status_code == 409


def test_manual_transaction_requires_owned_accounts(session):
    first, second = uuid4(), uuid4()
    create_account(session, first, AccountCreate(account_code='ACC001'))
    create_account(session, second, AccountCreate(account_code='ACC002'))
    item = TransactionCreate(
        transaction_id='TX123', sender_account='ACC001', receiver_account='ACC002',
        amount='100.00', currency='INR', occurred_at='2026-10-27T10:00:00+05:30',
    )
    with pytest.raises(HTTPException) as error:
        create_transaction(session, first, item)
    assert error.value.status_code == 422
    create_account(session, first, AccountCreate(account_code='ACC002'))
    result = create_transaction(session, first, item)
    assert result['sender_account'] == 'ACC001'
    assert result['amount'] == Decimal('100.00')
    assert list_transactions(session, second, 10, 0, None)['total'] == 0
    assert list_transactions(session, first, 10, 0, None)['total'] == 1


def test_csv_atomic_validation_and_deduplication(session):
    owner = uuid4()
    csv_input = '''transaction_id,sender_account,receiver_account,amount,currency,occurred_at,status
T1,A0001,A0002,2500.00,INR,2026-10-27T10:00:00+05:30,completed
T2,A0002,A0003,2400.00,INR,2026-10-27T10:02:00+05:30,completed
T3,A0003,A0001,2300.00,INR,2026-10-27T10:04:00+05:30,completed
'''
    parsed = parse_csv(csv_input.encode())
    batch = import_transactions(session, owner, 'sample.csv', parsed)
    assert (batch.total_rows, batch.imported_rows, batch.duplicate_rows) == (3, 3, 0)
    assert overview(session, owner)['accounts'] == 3
    again = import_transactions(session, owner, 'sample.csv', parsed)
    assert (again.total_rows, again.imported_rows, again.duplicate_rows) == (3, 0, 3)
    assert overview(session, owner)['transactions'] == 3
    bad = csv_input.replace('2400.00', '-1.00')
    with pytest.raises(HTTPException) as error:
        parse_csv(bad.encode())
    assert error.value.status_code == 422
    assert overview(session, owner)['transactions'] == 3
    conflict = csv_input.replace('2400.00', '2401.00')
    with pytest.raises(HTTPException) as error:
        import_transactions(session, owner, 'conflict.csv', parse_csv(conflict.encode()))
    assert error.value.status_code == 409
    assert overview(session, owner)['transactions'] == 3


def test_reject_invalid_timestamp_self_transfer_or_missing_columns():
    with pytest.raises(ValueError):
        TransactionCreate(transaction_id='T1', sender_account='A001', receiver_account='A001', amount='2', occurred_at='2026-10-27T10:00:00+05:30')
    with pytest.raises(ValueError):
        TransactionCreate(transaction_id='T1', sender_account='A001', receiver_account='A002', amount='2', occurred_at='2026-10-27T10:00:00')
    with pytest.raises(HTTPException):
        parse_csv(b'transaction_id,amount\nT1,20')


def test_foreign_key_owner_guards_cross_user_transfer(session):
    owner1, owner2 = uuid4(), uuid4()
    a = create_account(session, owner1, AccountCreate(account_code='ACC001'))
    b = create_account(session, owner2, AccountCreate(account_code='ACC002'))
    with pytest.raises(Exception):
        session.add(Transaction(owner_id=owner1, transaction_id='TX-SPOOF', sender_account_id=a.id, receiver_account_id=b.id,
                                amount=Decimal('100'), currency='INR', occurred_at=datetime.now(timezone.utc), status='completed'))
        session.commit()
    session.rollback()


def test_bundled_sample_data(session):
    from pathlib import Path
    sample = (Path(__file__).resolve().parents[2] / 'samples' / 'synthetic_transactions.csv').read_bytes()
    parsed = parse_csv(sample)
    assert parsed[1] == 8
    owner = uuid4()
    batch = import_transactions(session, owner, 'synthetic_transactions.csv', parsed)
    assert batch.imported_rows == 8
    assert overview(session, owner) == {
        'accounts': 11, 'transactions': 8, 'completed_transactions': 7, 'import_batches': 1,
    }
