"""Owner-scoped intelligence summaries and labeled synthetic scenario evaluation.

No labels are read by the fraud engine. All metrics are computed, never hard-coded.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.alerts import FraudAlert
from app.models.ledger import Transaction
from app.detection.engine import detect, PATTERN_NAMES
from app.detection.model import MODEL_VERSION


def intelligence_overview(db: Session, owner: UUID) -> dict:
    alerts = db.scalars(select(FraudAlert).where(FraudAlert.owner_id == owner)).all()
    patterns = Counter(a.pattern_type for a in alerts)
    severities = Counter('high' if a.risk_score >= 80 else 'medium' for a in alerts)
    accounts = {c for a in alerts for c in a.evidence.get('accounts', [])}
    tiers = Counter('high' if a.risk_score >= 85 else 'elevated' if a.risk_score >= 75 else 'moderate' for a in alerts)
    total = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.owner_id == owner)) or 0
    # Group by the dataset's own most recent event, not the wall clock: imported samples
    # might be historical, and the dashboard must not mislabel them as 'today'.
    rows = db.execute(select(Transaction.occurred_at, Transaction.amount, Transaction.status)
                      .where(Transaction.owner_id == owner)
                      .order_by(Transaction.occurred_at.desc()).limit(1200)).all()
    last_date = max((v[0].date() for v in rows), default=None)
    series = []
    if last_date:
        counts = Counter(t.date() for t, _, status in rows if status == 'completed')
        series = [{'day': (last_date - timedelta(days=i)).isoformat(),
                   'completed': counts[last_date - timedelta(days=i)]}
                  for i in range(6, -1, -1)]
    return {
        'total_transactions': total,
        'total_alerts': len(alerts),
        'flagged_accounts': len(accounts),
        'patterns': [{'key': key, 'name': PATTERN_NAMES[key], 'count': patterns[key]}
                     for key in ('circular', 'rapid', 'mule')],
        'severity': {'high': severities['high'], 'medium': severities['medium']},
        'risk_bands': {'high': tiers['high'], 'elevated': tiers['elevated'], 'moderate': tiers['moderate']},
        'average_risk': round(sum(a.risk_score for a in alerts) / len(alerts), 1) if alerts else 0,
        'average_anomaly_index': round(sum(a.anomaly_index for a in alerts) / len(alerts), 3) if alerts else 0,
        'sample_window': {'max_rows': 1200, 'end_date': last_date.isoformat() if last_date else None},
        'activity': series,
        'model_version': MODEL_VERSION,
        'data_note': 'Values reflect persisted synthetic-data investigation alerts; not confirmed fraud.',
    }


def _tx(ref: str, source: str, target: str, amount: int, instant: datetime) -> dict:
    return {'id': ref, 'source': source, 'target': target, 'amount': amount, 'at': instant}


def _evaluation_case(kind: str, seed: int):
    """Return (ground truth, input rows) with no labels in the rows themselves."""
    origin = datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(days=seed)
    prefix = f'EV{seed}'
    t = lambda i: origin + timedelta(seconds=i)
    if kind == 'circular':
        rows = [_tx(f'{prefix}01', f'{prefix}A', f'{prefix}B', 51000, t(0)),
                _tx(f'{prefix}02', f'{prefix}B', f'{prefix}C', 50400, t(45)),
                _tx(f'{prefix}03', f'{prefix}C', f'{prefix}A', 49900, t(95))]
    elif kind == 'rapid':
        rows = [_tx(f'{prefix}01', f'{prefix}A', f'{prefix}B', 35000, t(0)),
                _tx(f'{prefix}02', f'{prefix}B', f'{prefix}C', 34800, t(30)),
                _tx(f'{prefix}03', f'{prefix}C', f'{prefix}D', 34500, t(90))]
    elif kind == 'mule':
        rows = [_tx(f'{prefix}01', f'{prefix}A', f'{prefix}H', 15000, t(0)),
                _tx(f'{prefix}02', f'{prefix}B', f'{prefix}H', 16000, t(30)),
                _tx(f'{prefix}03', f'{prefix}C', f'{prefix}H', 14500, t(60)),
                _tx(f'{prefix}04', f'{prefix}H', f'{prefix}D', 43800, t(115))]
    else:
        # Ordinary payments, varied amounts and time spans. Avoid rapid flows,
        # fan-in concentration and closed loops while still exercising multiple edges.
        rows = [_tx(f'{prefix}{i:02d}', f'{prefix}P{i}', f'{prefix}Q{i}',
                    1000 + (i * 2413) % 67000, t(i * 7200)) for i in range(1, 8)]
    return rows


@lru_cache(maxsize=1)
def evaluate_synthetic_scenarios() -> dict:
    """Small reproducible functional benchmark, NOT real-world accuracy validation."""
    n_each = 8
    labels = ['normal'] * 16 + [v for v in ('circular', 'rapid', 'mule') for _ in range(n_each)]
    tp = fp = fn = tn = 0
    breakdown = defaultdict(lambda: {'cases': 0, 'detected': 0})
    for i, label in enumerate(labels):
        rows = _evaluation_case(label, i)
        inferred = detect(rows)
        positive = bool(inferred)
        actual = label != 'normal'
        tp += int(actual and positive)
        fp += int(not actual and positive)
        tn += int(not actual and not positive)
        fn += int(actual and not positive)
        breakdown[label]['cases'] += 1
        breakdown[label]['detected'] += int(positive)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        'model': 'IsolationForest + NetworkX evidence gate', 'model_version': MODEL_VERSION,
        'cases': len(labels), 'confusion_matrix': {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn},
        'precision': round(precision, 4), 'recall': round(recall, 4), 'f1': round(f1, 4),
        'by_scenario': [{'label': kind, **breakdown[kind]} for kind in ['normal','circular','rapid','mule']],
        'methodology': 'Independent, deliberately constructed labeled synthetic scenarios; classification based on whether at least one ML-gated pattern alert was produced.',
        'limitations': 'Not a holdout real-world banking dataset, not an unbiased fraud prevalence sample, and not evidence of production accuracy. Graph rules and evaluation cases share scenario assumptions.',
    }
