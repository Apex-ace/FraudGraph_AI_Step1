"""NetworkX graph patterns + real IsolationForest gate.

Only `completed` INR payments are analyzed together. The model never reads
transaction IDs or the simulator's known scenario tags. Alerts are hypotheses.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from itertools import islice
from uuid import UUID

import networkx as nx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.detection.model import score_pattern
from app.models.alerts import FraudAlert
from app.models.ledger import Account, Transaction

PATTERN_NAMES = {'circular': 'Circular fund movement', 'rapid': 'Rapid transfer chain', 'mule': 'Potential mule-account flow'}
MAX_LOOKBACK = 600
MAX_ALERT_CANDIDATES = 35


def read_transactions(db: Session, owner: UUID):
    src, dst = aliased(Account), aliased(Account)
    result = db.execute(select(Transaction, src.account_code, dst.account_code)
                        .join(src, (Transaction.owner_id == src.owner_id) & (Transaction.sender_account_id == src.id))
                        .join(dst, (Transaction.owner_id == dst.owner_id) & (Transaction.receiver_account_id == dst.id))
                        .where(Transaction.owner_id == owner, Transaction.status == 'completed', Transaction.currency == 'INR')
                        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(MAX_LOOKBACK)).all()
    return sorted([{'id': t.transaction_id, 'source': s, 'target': d, 'amount': float(t.amount),
                    'at': t.occurred_at if t.occurred_at.tzinfo else t.occurred_at.replace(tzinfo=timezone.utc)}
                   for t,s,d in result], key=lambda x: (x['at'], x['id']))


def _within(transfers, minutes):
    return transfers and 0 < (transfers[-1]['at'] - transfers[0]['at']).total_seconds() <= 60 * minutes


def _amounts_coherent(transfers, tolerance=0.75):
    values = [t['amount'] for t in transfers]
    return min(values) / max(values) >= tolerance


def find_patterns(rows):
    """Returns candidate (type, evidence transactions). Deterministic, ID-tag agnostic."""
    if len(rows) < 3:
        return []
    graph = nx.DiGraph()
    by_edge = defaultdict(list)
    incoming, outgoing = defaultdict(list), defaultdict(list)
    for tx in rows:
        graph.add_edge(tx['source'],tx['target'])
        by_edge[(tx['source'],tx['target'])].append(tx)
        incoming[tx['target']].append(tx)
        outgoing[tx['source']].append(tx)
    findings, fingerprints = [], set()

    def add(kind, items):
        ordered = sorted(items, key=lambda x:(x['at'],x['id']))
        key = (kind, tuple(sorted(t['id'] for t in ordered)))
        if key in fingerprints or len(findings) >= MAX_ALERT_CANDIDATES:
            return
        fingerprints.add(key)
        findings.append((kind,ordered))

    # Directed simple cycles <= 4 nodes. Validate chronological transfers.
    # Limit complexity by using only the newest 100 events for cycle candidates.
    cycle_graph = nx.DiGraph((t['source'], t['target']) for t in rows[-120:])
    for cycle in islice(nx.simple_cycles(cycle_graph, length_bound=4), 70):
        if len(cycle)<3 or len(findings)>=MAX_ALERT_CANDIDATES:
            continue
        for rotation in range(len(cycle)):
            rotated=cycle[rotation:]+cycle[:rotation]
            edge_paths=[by_edge[(rotated[i],rotated[(i+1)%len(rotated)])][-8:] for i in range(len(rotated))]
            matched=[]
            for path in edge_paths:
                candidate=next((t for t in path if not matched or t['at']>matched[-1]['at']),None)
                if candidate is None:break
                matched.append(candidate)
            if len(matched)==len(cycle) and _within(matched,15) and _amounts_coherent(matched):
                add('circular',matched)
                break

    # A->B->C->D in at most 8 minutes, preserving order and at least 75% value.
    for first in rows[-120:]:
        if len(findings)>=MAX_ALERT_CANDIDATES:break
        middle_candidates=(r for r in outgoing[first['target']] if r['at']>first['at'] and (r['at']-first['at']).total_seconds()<=480)
        for middle in islice(middle_candidates,8):
            last_candidates=(r for r in outgoing[middle['target']] if r['at']>middle['at'] and (r['at']-first['at']).total_seconds()<=480)
            for last in islice(last_candidates,8):
                if len({first['source'],first['target'],middle['target'],last['target']})!=4:continue
                trio=[first,middle,last]
                if _amounts_coherent(trio):add('rapid',trio);break
            if len(findings)>=MAX_ALERT_CANDIDATES:break

    # >=3 unique senders feeding an account then one onward withdrawal.
    for hub, received in incoming.items():
        if len(findings)>=MAX_ALERT_CANDIDATES:break
        for payout in outgoing.get(hub,[])[-10:]:
            candidates=[t for t in received if 0<(payout['at']-t['at']).total_seconds()<=900
                        and t['source']!=payout['target']]
            latest_by_source={}
            for candidate in candidates:latest_by_source[candidate['source']]=candidate
            selected=sorted(latest_by_source.values(),key=lambda t:t['at'])[-3:]
            if len(selected)!=3:continue
            total_in=sum(t['amount'] for t in selected)
            if 0.6*total_in<=payout['amount']<=1.25*total_in:
                add('mule',selected+[payout])
    return findings


def detect(rows):
    """ML MUST independently predict an anomaly before an alert is emitted."""
    findings=[]
    strengths={'circular':0.92,'rapid':0.84,'mule':0.88}
    for kind, evidence in find_patterns(rows):
        ml=score_pattern(evidence)
        # Genuine ML gate: graph evidence alone never produces an alert.
        risk=round(100*(0.55*strengths[kind]+0.45*ml['anomaly_index']),1)
        if not ml['is_anomaly'] or risk<70:
            continue
        ids=[t['id'] for t in evidence]
        accounts=sorted({t['source'] for t in evidence}|{t['target'] for t in evidence})
        fingerprint=sha256((kind+':' + '|'.join(sorted(ids))).encode('utf-8')).hexdigest()
        findings.append({
            'fingerprint':fingerprint,
            'pattern_type':kind, 'name':PATTERN_NAMES[kind], 'risk_score':risk,
            'anomaly_index':ml['anomaly_index'], 'model_version':ml['model_version'],
            'summary':f'{PATTERN_NAMES[kind]}: {len(evidence)} linked transfers among {len(accounts)} accounts.',
            'synthetic':all(t['id'].startswith('FGSIM_') for t in evidence),
            'evidence':{
                'transaction_ids':ids, 'accounts':accounts, 'model_decision_margin':ml['decision_margin'],
                'feature_summary':ml['feature_summary'],
                'transfers':[{'id':t['id'], 'source':t['source'],'target':t['target'],
                              'amount':t['amount'],'at':t['at'].isoformat()} for t in evidence],
            },
        })
    return findings


def serialize_alert(a):
    return {'id':str(a.id), 'pattern_type':a.pattern_type, 'name':PATTERN_NAMES.get(a.pattern_type,a.pattern_type),
            'severity':'high' if a.risk_score>=80 else 'medium',
            'risk_score':a.risk_score, 'anomaly_index':a.anomaly_index, 'model_version':a.model_version,
            'summary':a.summary, 'status':a.status, 'synthetic':a.synthetic,
            'accounts':a.evidence.get('accounts', []),'transaction_ids':a.evidence.get('transaction_ids', []),
            'evidence':a.evidence, 'at':(a.created_at if a.created_at.tzinfo else a.created_at.replace(tzinfo=timezone.utc)).isoformat()}


def analyze_and_persist(db: Session, owner: UUID):
    """Idempotent and owner-isolated. Returns ONLY freshly detected alerts."""
    candidates=detect(read_transactions(db,owner))
    if not candidates:return []
    known=set(db.scalars(select(FraudAlert.fingerprint).where(
        FraudAlert.owner_id==owner,FraudAlert.fingerprint.in_([c['fingerprint'] for c in candidates]))).all())
    fresh=[]
    for c in candidates:
        if c['fingerprint'] in known:continue
        known.add(c['fingerprint'])
        alert=FraudAlert(owner_id=owner,**{k:v for k,v in c.items() if k!='name'})
        db.add(alert)
        fresh.append(alert)
    if not fresh:return []
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request may have inserted the same fingerprint first.
        # Unique database constraints ensure only one persisted alert.
        db.rollback()
        return []
    return [serialize_alert(a) for a in fresh]


def list_alerts(db: Session, owner: UUID, limit=60):
    return [serialize_alert(a) for a in db.scalars(select(FraudAlert).where(FraudAlert.owner_id==owner)
            .order_by(FraudAlert.created_at.desc()).limit(limit)).all()]


async def scan_and_notify(owner: UUID):
    """Run outside the request thread; scan after a committed transaction/import."""
    import logging
    from starlette.concurrency import run_in_threadpool
    from app.core.database import get_engine
    from app.sockets.server import sio
    log = logging.getLogger(__name__)
    def work():
        with Session(get_engine()) as session:
            return analyze_and_persist(session, owner)
    try:
        fresh = await run_in_threadpool(work)
        for alert in fresh:
            await sio.emit('fraud_alert_detected', alert, to=f'user:{owner}')
    except Exception:
        log.exception('ML scan error for owner %s', owner)
