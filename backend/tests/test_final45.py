"""Focused integration tests for the last-mile demo additions."""
from uuid import UUID, uuid4
from pathlib import Path
from sqlalchemy.orm import Session
import pytest

from app.core.config import settings
from app.core.database import get_engine, init_db
from app.core.local_auth import register_user
from app.services.intelligence import intelligence_overview, evaluate_synthetic_scenarios
from app.services.demo_case import prepare_case
from app.detection.engine import list_alerts
from app.services.simulator import graph_snapshot

@pytest.fixture
def setup_local(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'db_provider', 'sqlite')
    monkeypatch.setattr(settings, 'auth_mode', 'local')
    monkeypatch.setattr(settings, 'app_env', 'development')
    monkeypatch.setattr(settings, 'local_sqlite_path', str(tmp_path / 'final45.db'))
    monkeypatch.setattr(settings, 'local_auth_secret_file', str(tmp_path / 'secret.key'))
    get_engine.cache_clear()
    init_db()
    yield
    get_engine().dispose()
    get_engine.cache_clear()

def test_evaluation_is_computed_from_real_predictions():
    result=evaluate_synthetic_scenarios()
    cm=result['confusion_matrix']
    assert sum(cm.values())==result['cases']==40
    assert cm['tp']>0 and cm['tn']>0
    assert result['precision']==round(cm['tp']/(cm['tp']+cm['fp']),4)
    assert 'Not a holdout' in result['limitations']

def test_case_is_idempotent_and_shows_database_evidence(setup_local):
    owner=UUID(register_user('example@innova.test','the-long-enough-pass')['user']['id'])
    result=prepare_case(owner)
    assert result['created_transactions']==10
    assert result['featured_alert'] is not None
    assert result['total_demo_alerts']>0
    alert=result['featured_alert']
    again=prepare_case(owner)
    assert again['created_transactions']==0
    with Session(get_engine()) as db:
        overview=intelligence_overview(db,owner)
        assert overview['total_transactions']==10
        assert overview['total_alerts']>=1
        assert overview['flagged_accounts']>0
        assert sum(p['count'] for p in overview['patterns'])==overview['total_alerts']
        snapshot=graph_snapshot(db,owner,500)
        evidence=set(alert['transaction_ids'])
        assert any(evidence.intersection(edge['transaction_ids']) for edge in snapshot['edges'])

def test_owner_isolation(setup_local):
    first=UUID(register_user('one@innova.test','the-long-enough-pass')['user']['id'])
    second=UUID(register_user('two@innova.test','the-long-enough-pass')['user']['id'])
    prepare_case(first)
    with Session(get_engine()) as db:
        assert intelligence_overview(db,second)['total_alerts']==0
        assert not graph_snapshot(db,second)['nodes']

def test_authenticated_lan_and_intelligence_routes(setup_local):
    from fastapi.testclient import TestClient
    from app.main import api
    with TestClient(api) as client:
        res=client.post('/api/auth/register',json={'email':'lan@example.com','password':'long-password-here'})
        assert res.status_code==201
        headers={'Authorization':'Bearer '+res.json()['access_token']}
        assert client.get('/api/intelligence/overview').status_code==401
        eval_res=client.get('/api/intelligence/evaluation',headers=headers)
        assert eval_res.status_code==200
        start=client.post('/api/intelligence/demo/prepare',headers=headers)
        assert start.status_code==200, start.text
        assert start.json()['featured_alert'] is not None
        metric=client.get('/api/intelligence/overview',headers=headers)
        assert metric.status_code==200
        assert metric.json()['total_transactions']==10
