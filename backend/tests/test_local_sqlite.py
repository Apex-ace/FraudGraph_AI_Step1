"""Run: python -m pytest -q tests/test_local_sqlite.py"""
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_engine, init_db
from app.core.local_auth import login_user, register_user, verify_local_token
from app.services import ledger
from app.services.simulator import generate_batch
from app.models.ledger import Base


@pytest.fixture
def local_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'db_provider', 'sqlite')
    monkeypatch.setattr(settings, 'auth_mode', 'local')
    monkeypatch.setattr(settings, 'local_sqlite_path', str(tmp_path / 'ledger.db'))
    monkeypatch.setattr(settings, 'local_auth_secret_file', str(tmp_path / 'jwt_secret.key'))
    get_engine.cache_clear()
    init_db()
    yield tmp_path
    engine = get_engine()
    engine.dispose()
    get_engine.cache_clear()


def test_sqlite_local_registration_and_persistence(local_db):
    session = register_user('Tester@Example.org', 'a-local-demo-password')
    assert session['user']['email'] == 'tester@example.org'
    token = session['access_token']
    assert verify_local_token(token)['id'] == session['user']['id']
    assert login_user('tester@example.org', 'a-local-demo-password')['user']['id'] == session['user']['id']
    with pytest.raises(Exception):
        login_user('tester@example.org', 'wrong-password')
    with Session(get_engine()) as db:
        assert db.execute(text('PRAGMA foreign_keys')).scalar_one() == 1
        assert db.execute(text('PRAGMA journal_mode')).scalar_one() == 'wal'
        assert db.execute(text("SELECT count(*) FROM sqlite_master WHERE type='table' AND name in ('accounts','transactions','import_batches','fraud_alerts','local_users')")).scalar_one() == 5
    assert (local_db/'ledger.db').exists()
    assert (local_db/'jwt_secret.key').exists()


def test_import_1000_rows_in_sqlite_without_supabase(local_db):
    owner = uuid4()
    csvpath = Path(__file__).resolve().parents[3] / 'Team_Innova_FraudGraph_1000_Transactions.csv'
    # The sample is shipped separately; fallback to the 8-row source sample.
    if not csvpath.exists():
        csvpath = Path(__file__).resolve().parents[2] / 'samples/synthetic_transactions.csv'
    parsed = ledger.parse_csv(csvpath.read_bytes())
    with Session(get_engine()) as db:
        result = ledger.import_transactions(db, owner, csvpath.name, parsed)
        assert result.imported_rows == parsed[1]
        again = ledger.import_transactions(db, owner, csvpath.name, parsed)
        assert again.duplicate_rows == parsed[1]
        assert ledger.overview(db, owner)['transactions'] == parsed[1]
    # A second DB session sees the already committed rows (durability).
    with Session(get_engine()) as db:
        assert ledger.overview(db, owner)['transactions'] == parsed[1]


def test_local_login_and_health_api(local_db):
    from app.main import api
    with TestClient(api) as client:
        assert client.get('/api/health').status_code == 200
        registered = client.post('/api/auth/register', json={
            'email': 'owner@teaminnova.org', 'password': 'testing-123456',
        })
        assert registered.status_code == 201, registered.text
        token = registered.json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        assert client.get('/api/me', headers=headers).status_code == 200
        db = client.get('/api/health/database', headers=headers)
        assert db.status_code == 200 and db.json()['database'] == 'sqlite-local'
        assert client.get('/api/overview', headers=headers).json()['transactions'] == 0
        assert client.get('/api/overview').status_code == 401


def test_simulation_ml_pipeline_on_file_sqlite(local_db):
    from app.detection.engine import analyze_and_persist, list_alerts
    user = register_user('demo@teaminnova.org', 'strong-demo-password')
    from uuid import UUID
    owner = UUID(user['user']['id'])
    assert len(generate_batch(owner, 0, True)) == 24
    for i in range(10):
        assert len(generate_batch(owner, i, False)) == 1
    with Session(get_engine()) as db:
        alerts = analyze_and_persist(db, owner)
        assert alerts
        assert all(alert['risk_score'] >= 70 for alert in alerts)
        assert len(list_alerts(db, owner)) == len(alerts)
        assert not analyze_and_persist(db, owner)
