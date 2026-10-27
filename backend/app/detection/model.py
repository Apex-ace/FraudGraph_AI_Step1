"""Reproducible demo Isolation Forest, trained on synthetic normal-behavior reference.

This model is trained (not hard-coded rules), but it is NOT calibrated to real bank fraud.
Never consume simulator FGSIM_ labels in feature calculation or scoring.
"""
from functools import lru_cache
import math

import numpy as np
from sklearn.ensemble import IsolationForest

MODEL_VERSION = 'iforest-synthetic-baseline-v1'
FEATURE_NAMES = ('log_mean_amount', 'transactions_per_minute', 'max_fan_in',
                 'max_fan_out', 'amount_coefficient_variation', 'log_duration_seconds', 'distinct_accounts')


def features(rows):
    """Rows are dictionaries with source, target, amount, at; no ID or scenario labels."""
    amounts = np.array([float(r['amount']) for r in rows], dtype=float)
    seconds = sorted(float(r['at'].timestamp()) for r in rows)
    duration = max(seconds[-1]-seconds[0], 1.0)
    incoming, outgoing, codes = {}, {}, set()
    for row in rows:
        incoming[row['target']] = incoming.get(row['target'], 0) + 1
        outgoing[row['source']] = outgoing.get(row['source'], 0) + 1
        codes.update((row['source'], row['target']))
    result = [math.log10(float(amounts.mean()) + 1),
              len(rows) / max(duration / 60.0, 0.05),
              max(incoming.values(), default=0), max(outgoing.values(), default=0),
              float(amounts.std()/amounts.mean()) if amounts.mean() else 0.0,
              math.log10(duration+1), len(codes)]
    return dict(zip(FEATURE_NAMES, [round(float(n), 5) for n in result]))


@lru_cache(maxsize=1)
def reference_model():
    """Prepares a deterministic synthetic normal baseline once per backend process."""
    rng = np.random.default_rng(2026)
    sample = []
    for _ in range(1400):
        n = int(rng.integers(2, 6))
        amount = float(np.clip(rng.lognormal(9.1, 1.0), 150, 130000))
        duration = float(rng.uniform(15*60, 6*3600))
        fan = int(rng.choice([1, 1, 1, 2]))
        sample.append([
            math.log10(amount+1),
            n/(duration/60),
            fan, fan,
            float(rng.uniform(0.12, 0.85)),
            math.log10(duration+1),
            n+1,
        ])
    model = IsolationForest(n_estimators=100, contamination=0.04, random_state=2026, n_jobs=1)
    model.fit(np.asarray(sample))
    return model


def score_pattern(rows):
    f = features(rows)
    vector = np.asarray([[f[k] for k in FEATURE_NAMES]])
    model = reference_model()
    margin = float(model.decision_function(vector)[0])
    # decision_function below zero = model outlier. Number below is a demo index,
    # not a calibrated probability of fraud.
    anomaly_index = float(np.clip(0.5 - margin * 4.5, 0, 1))
    return {'is_anomaly': bool(model.predict(vector)[0] == -1),
            'anomaly_index': round(anomaly_index, 3),
            'decision_margin': round(margin, 5),
            'feature_summary': f,
            'model_version': MODEL_VERSION}
