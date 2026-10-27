"""Supervised synthetic-behavior screening for graph pattern candidates.

Training and threshold selection use distinct synthetic seeds. Evaluation uses a
third, held-out seed. Neither IDs nor scenario names are model inputs.
This is not a real bank fraud probability estimator.
"""
from collections import Counter
from functools import lru_cache
import math

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import f1_score

from app.detection.synthetic_cases import generate

MODEL_VERSION = 'extratrees-synthetic-behavior-v2'
FEATURE_NAMES = ('log_mean_amount', 'transactions_per_minute', 'max_fan_in',
                 'max_fan_out', 'amount_coefficient_variation', 'log_duration_seconds', 'distinct_accounts')


def features(rows):
    amounts = np.array([float(r['amount']) for r in rows], dtype=float)
    seconds = sorted(float(r['at'].timestamp()) for r in rows)
    duration = max(seconds[-1]-seconds[0],1.0)
    incoming,outgoing,codes = Counter(),Counter(),set()
    for row in rows:
        incoming[row['target']]+=1
        outgoing[row['source']]+=1
        codes.update((row['source'],row['target']))
    vals=[math.log10(float(amounts.mean())+1),len(rows)/max(duration/60,.05),
          max(incoming.values(),default=0),max(outgoing.values(),default=0),
          float(amounts.std()/amounts.mean()) if amounts.mean() else 0,
          math.log10(duration+1),len(codes)]
    return dict(zip(FEATURE_NAMES,[round(float(x),5) for x in vals]))


def _infer_kind(rows):
    incoming,outgoing=Counter(),Counter()
    for r in rows:
        incoming[r['target']]+=1
        outgoing[r['source']]+=1
    if any(incoming[n]>=3 and outgoing[n] for n in incoming):
        return 'mule'
    if rows[0]['source']==rows[-1]['target']:
        return 'circular'
    return 'rapid'


def _vector(rows,kind):
    data=features(rows)
    amounts=np.array([float(r['amount']) for r in rows],dtype=float)
    times=sorted(x['at'].timestamp() for x in rows)
    gaps=np.diff(times)
    hub=rows[-1]['source']
    fan=sum(r['target']==hub for r in rows[:-1])
    return [data[k] for k in FEATURE_NAMES]+[
        len(rows),
        float(amounts[-1]/amounts[0]),
        float(amounts.min()/amounts.max()),
        float(np.std(gaps)/(np.mean(gaps)+1)) if len(gaps) else 0,
        float(np.median(gaps)) if len(gaps) else 0,
        float(amounts[-1]/max(1,amounts[:-1].sum())),
        int(kind=='circular'),int(kind=='rapid'),int(kind=='mule'),fan,
    ]


def _candidate_training_records(seed,per_kind,offset):
    # Local import avoids a circular module import during application startup.
    from app.detection.engine import find_patterns
    records=[]
    cases=generate(seed,per_kind,offset)
    for rows,truth,_name in cases:
        for kind,selected in find_patterns(rows)[:3]:
            records.append((_vector(selected,kind),truth))
    return records,cases


def _score_cases(clf,cases):
    from app.detection.engine import find_patterns
    all_features,case_indices=[],[]
    for i,(rows,_,_) in enumerate(cases):
        for kind,selected in find_patterns(rows)[:3]:
            all_features.append(_vector(selected,kind))
            case_indices.append(i)
    scores=np.zeros(len(cases),dtype=float)
    if all_features:
        values=clf.predict_proba(np.asarray(all_features))[:,1]
        for i,value in zip(case_indices,values):
            scores[i]=max(scores[i],float(value))
    return scores


@lru_cache(maxsize=1)
def reference_model():
    """Train once per worker. Calibration data is disjoint from final test data."""
    records,_ = _candidate_training_records(45067,110,100000)
    X=np.asarray([v for v,_ in records]);y=np.asarray([label for _,label in records])
    clf=ExtraTreesClassifier(n_estimators=130,min_samples_leaf=5,random_state=31,n_jobs=1)
    clf.fit(X,y)
    _,validation=_candidate_training_records(21765,40,300000)
    scores=_score_cases(clf,validation)
    actual=np.asarray([truth for _,truth,_ in validation])
    options=np.arange(.25,.851,.025)
    # Select solely on development/validation cases; held-out test is never consulted.
    threshold=float(max(options,key=lambda cutoff:(f1_score(actual,scores>=cutoff,zero_division=0),cutoff)))
    return clf,threshold


def score_pattern(rows,kind=None):
    kind=kind or _infer_kind(rows)
    model,threshold=reference_model()
    probability=float(model.predict_proba([_vector(rows,kind)])[0,1])
    return {
        'is_anomaly':probability>=threshold,
        'anomaly_index':round(probability,3),
        'decision_margin':round(probability-threshold,5),
        'feature_summary':{**features(rows),'graph_pattern':kind,
                           'candidate_model_score':round(probability,3),
                           'synthetic_validation_threshold':round(threshold,3)},
        'model_version':MODEL_VERSION,
    }
