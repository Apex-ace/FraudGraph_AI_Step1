"""Run: python -m pytest -q tests/test_detection.py"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.ledger import Base, Account, Transaction
from app.models.alerts import FraudAlert
from app.detection.engine import detect, analyze_and_persist, list_alerts
from app.detection.model import score_pattern

T0=datetime(2026, 10, 27, tzinfo=timezone.utc)


def make_rows(pairs, interval=3, prefix='NORMAL'):
    return [{'source':s,'target':t,'amount':a,'at':T0+timedelta(seconds=i*interval),
             'id':f'{prefix}{i}'} for i,(s,t,a) in enumerate(pairs)]


def test_model_triggers_independent_of_simulator_ids():
    for pattern,pairs in [
        ('circular',[('A','B',50000),('B','C',49500),('C','A',49000)]),
        ('rapid',[('A','B',35000),('B','C',34750),('C','D',34500)]),
        ('mule',[('A','B',15000),('C','B',15000),('D','B',15000),('B','E',44000)]),
    ]:
        records=make_rows(pairs, prefix='IMPORT_')
        assert score_pattern(records)['is_anomaly']
        alerts=detect(records)
        assert any(a['pattern_type']==pattern for a in alerts)
        assert all('FGSIM' not in a['fingerprint'] for a in alerts)


def test_normal_unconnected_transfers_do_not_trigger():
    rows=make_rows([('A','B',500),('C','D',1300),('E','F',2000)], interval=3600)
    assert detect(rows)==[]


def test_persisted_alerts_are_idempotent_and_user_isolated():
    engine=create_engine('sqlite+pysqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    owner1,owner2=uuid4(),uuid4()
    rows=make_rows([('A','B',50000),('B','C',49500),('C','A',49000)],prefix='EXTERNAL_')
    with Session(engine) as db:
        for owner in (owner1,owner2):
            accounts={}
            for code in ('A','B','C'):
                a=Account(owner_id=owner,account_code=code)
                db.add(a);db.flush();accounts[code]=a
            for row in rows:
                db.add(Transaction(owner_id=owner,transaction_id=row['id'],sender_account_id=accounts[row['source']].id,
                                   receiver_account_id=accounts[row['target']].id,amount=row['amount'],
                                   occurred_at=row['at'],currency='INR',status='completed'))
            db.commit()
        fresh=analyze_and_persist(db,owner1)
        assert len(fresh)==1
        assert fresh[0]['risk_score']>=70
        assert not fresh[0]['synthetic']
        assert len(analyze_and_persist(db,owner1))==0
        assert len(list_alerts(db,owner2))==0
        assert len(analyze_and_persist(db,owner2))==1
        assert len(list_alerts(db,owner1))==1
    engine.dispose()
