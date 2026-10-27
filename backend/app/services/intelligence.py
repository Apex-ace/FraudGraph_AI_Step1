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


# Synthetic benchmark has independent test seed and identifiers. The test cases
# share a *scenario generation family* with training: NOT a real holdout bank set.
# Variation and overlap intentionally prevent trivial 100% discrimination.
from app.detection.synthetic_cases import KINDS, FRAUD, generate


@lru_cache(maxsize=1)
def evaluate_synthetic_scenarios() -> dict:
    """Evaluate the unchanged deployed detector on untouched synthetic test cases."""
    cases = generate(seed=20261027, per_kind=40, offset=0)
    tp = fp = fn = tn = 0
    breakdown = defaultdict(lambda: {'cases': 0, 'detected': 0, 'correct': 0})
    for rows,actual,label in cases:
        predicted = bool(detect(rows))
        tp += int(actual and predicted)
        fp += int(not actual and predicted)
        tn += int(not actual and not predicted)
        fn += int(actual and not predicted)
        breakdown[label]['cases'] += 1
        breakdown[label]['detected'] += int(predicted)
        breakdown[label]['correct'] += int(predicted == actual)
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    specificity = tn / (tn + fp) if tn + fp else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    accuracy = (tp + tn) / len(cases)
    return {
        'model': 'NetworkX + synthetic-trained ExtraTreesClassifier',
        'model_version': MODEL_VERSION,
        'cases': len(cases),
        'confusion_matrix': {'tp':tp,'fp':fp,'tn':tn,'fn':fn},
        'precision':round(precision,4), 'recall':round(recall,4), 'f1':round(f1,4),
        'specificity':round(specificity,4), 'accuracy':round(accuracy,4),
        'false_positive_rate':round(1-specificity,4),
        'by_scenario':[{'label':name,**breakdown[name]} for name in KINDS],
        'methodology':('360 reproducible synthetic case-level tests. ' 
           'Training seed 45067, threshold calibration seed 21765, test seed 20261027. '
           'Neither scenario IDs nor labels are provided to the ML model.'),
        'limitations':('NOT measured on real bank fraud. Training, calibration, and evaluation use '
           'the same synthetic scenario families, though separate seeded examples; results may overstate '
           'generalization. Similar legitimate and suspicious flows can be indistinguishable without '
           'account and payment-purpose context. No metric is forced to a target value.'),
    }
