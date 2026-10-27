"""Run with the installed backend requirements: python -m pytest -q tests/test_simulator.py"""
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.ledger import Base, Transaction
from app.models.alerts import FraudAlert
from app.detection.engine import analyze_and_persist, list_alerts
from app.services import simulator


@pytest.fixture
def fake_db(monkeypatch):
    engine = create_engine('sqlite+pysqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    @event.listens_for(engine, 'connect')
    def fk_on(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    monkeypatch.setattr(simulator, '_db_session', lambda: Session(engine))
    yield engine
    engine.dispose()


def test_synthetic_transactions_are_persisted_and_owner_scoped(fake_db):
    owner_a, owner_b = uuid4(), uuid4()
    seeded = simulator.generate_batch(owner_a, 0, True)
    assert len(seeded) == 24
    assert all(tx['synthetic'] and tx['transaction_id'].startswith('FGSIM_') for tx in seeded)
    assert simulator.generate_batch(owner_b, 0, True)
    for step in range(10):
        assert len(simulator.generate_batch(owner_a, step, False)) == 1
    with Session(fake_db) as db:
        a = simulator.graph_snapshot(db, owner_a)
        b = simulator.graph_snapshot(db, owner_b)
        assert a['simulated_count'] == 34
        assert b['simulated_count'] == 24
        assert a['total_transactions'] == 34
        assert len(a['nodes']) > 8
        alerts=analyze_and_persist(db,owner_a)
        assert alerts
        a=simulator.graph_snapshot(db,owner_a)
        assert a['scenarios']
        assert all(e['risk_score'] >= 70 for e in a['scenarios'])
        assert all(e['anomaly_index'] >= 0.5 for e in a['scenarios'])


def test_reset_clears_only_generated_transactions(fake_db):
    owner_a, owner_b = uuid4(), uuid4()
    simulator.generate_batch(owner_a, 0, True)
    simulator.generate_batch(owner_b, 0, True)
    with Session(fake_db) as db:
        analyze_and_persist(db,owner_a)
    assert simulator.reset_simulated_data(owner_a) == 24
    with Session(fake_db) as db:
        assert simulator.simulated_count(db, owner_a) == 0
        assert simulator.simulated_count(db, owner_b) == 24
        assert all(not a['synthetic'] for a in list_alerts(db, owner_a))


def test_manual_transaction_cannot_use_reserved_simulation_id():
    from pydantic import ValidationError
    from app.schemas.ledger import TransactionCreate
    with pytest.raises(ValidationError):
        TransactionCreate(
            transaction_id='FGSIM_N_FAKE', sender_account='A001', receiver_account='B001',
            amount='10.00', occurred_at='2026-10-27T10:00:00+05:30',
        )
