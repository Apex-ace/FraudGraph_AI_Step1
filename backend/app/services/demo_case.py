"""Explicit, idempotent owner-scoped hackathon case seeding (development only)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.detection.engine import analyze_and_persist, list_alerts
from app.models.ledger import Account, Transaction

PREFIX = 'FGDEMO_'
CHAINS = [
    ('circular', [('A', 'B', 50000), ('B', 'C', 49500), ('C', 'A', 49000)]),
    ('rapid', [('D', 'E', 36000), ('E', 'F', 35700), ('F', 'G', 35200)]),
    ('mule', [('H', 'M', 16000), ('I', 'M', 15000), ('J', 'M', 14500), ('M', 'K', 43800)]),
]


def prepare_case(owner: UUID) -> dict:
    with Session(get_engine()) as db:
        all_codes = {f'DEMO_{code}' for _, seq in CHAINS for source, dest, _ in seq for code in (source, dest)}
        accounts = {a.account_code: a for a in db.scalars(select(Account).where(
            Account.owner_id == owner, Account.account_code.in_(all_codes))).all()}
        for code in sorted(all_codes):
            if code not in accounts:
                accounts[code] = Account(owner_id=owner, account_code=code, label='Guided demonstration account · synthetic')
                db.add(accounts[code])
        db.flush()
        transaction_ids = [f'{PREFIX}{kind.upper()}_{i}' for kind, chain in CHAINS for i, _ in enumerate(chain)]
        existing = set(db.scalars(select(Transaction.transaction_id).where(
            Transaction.owner_id == owner, Transaction.transaction_id.in_(transaction_ids))).all())
        new_ids = []
        # Use current event time so case remains in the newest 600 transactions.
        # Separating clusters by 20 minutes avoids accidentally merging independent patterns.
        origin = datetime.now(timezone.utc).replace(microsecond=0)
        for offset, (kind, chain) in enumerate(CHAINS):
            for i, (source, target, amount) in enumerate(chain):
                ref = f'{PREFIX}{kind.upper()}_{i}'
                if ref in existing: continue
                db.add(Transaction(owner_id=owner, transaction_id=ref,
                    sender_account_id=accounts[f'DEMO_{source}'].id,
                    receiver_account_id=accounts[f'DEMO_{target}'].id,
                    amount=Decimal(amount), currency='INR', status='completed',
                    occurred_at=origin + timedelta(minutes=offset*20, seconds=i*40)))
                new_ids.append(ref)
        if new_ids: db.commit()
        fresh = analyze_and_persist(db, owner)
        existing_alerts = list_alerts(db, owner, limit=100)
        matching = [a for a in existing_alerts if any(str(ref).startswith(PREFIX) for ref in a['transaction_ids'])]
        matching.sort(key=lambda a: (a['risk_score'], a['at']), reverse=True)
        return {'created_transactions': len(new_ids), 'new_alerts': fresh,
                'featured_alert': matching[0] if matching else None,
                'total_demo_alerts': len(matching),
                'note': 'Synthetic case, not a real payment or an allegation of fraud.'}
