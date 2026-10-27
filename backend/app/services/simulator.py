"""Per-user, opt-in, bounded synthetic transaction stream. No external payment system."""
from __future__ import annotations

import asyncio
import logging
import random
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, aliased
from starlette.concurrency import run_in_threadpool

from app.core.database import get_engine
from app.models.ledger import Account, Transaction
from app.sockets.server import sio

log = logging.getLogger(__name__)
PREFIX = "FGSIM_"
MAX_PER_OWNER = 1200
MAX_TICKS = 120
MIN_INTERVAL = 2
MAX_INTERVAL = 10
SIM_CODES = (
    [(f"SYN_U{i:02d}", f"Consumer {i:02d} · Synthetic") for i in range(1, 9)]
    + [(f"SYN_B{i:02d}", f"Bank {i:02d} · Synthetic") for i in range(1, 5)]
    + [(f"SYN_W{i:02d}", f"Wallet {i:02d} · Synthetic") for i in range(1, 5)]
    + [(f"SYN_M{i:02d}", f"Merchant {i:02d} · Synthetic") for i in range(1, 6)]
)
KIND_NAMES = {"U": "customer", "B": "bank", "W": "wallet", "M": "merchant"}
SCENARIO_RE = re.compile(r"^FGSIM_([CRM])(\d+)_(\d+)_")


def utc_now():
    return datetime.now(timezone.utc)


def _db_session():
    return Session(get_engine())


def simulated_count(db: Session, owner: UUID) -> int:
    return db.scalar(select(func.count()).select_from(Transaction).where(
        Transaction.owner_id == owner, Transaction.transaction_id.like("FGSIM\\_%", escape="\\")
    )) or 0


def _seed_accounts(db: Session, owner: UUID):
    codes = {code for code, _ in SIM_CODES}
    existing = {a.account_code: a for a in db.scalars(
        select(Account).where(Account.owner_id == owner, Account.account_code.in_(codes))
    ).all()}
    for code, label in SIM_CODES:
        if code not in existing:
            account = Account(owner_id=owner, account_code=code, label=label)
            db.add(account)
            db.flush()
            existing[code] = account
    return existing


def _make_tx(owner: UUID, accounts, sender: str, receiver: str, amount: int, tag: str):
    return Transaction(
        owner_id=owner, transaction_id=f"FGSIM_{tag}_{uuid4().hex[:12]}",
        sender_account_id=accounts[sender].id, receiver_account_id=accounts[receiver].id,
        amount=Decimal(amount), currency="INR", occurred_at=utc_now(), status="completed",
    )


def _format_tx(t: Transaction, accounts: dict):
    reverse = {a.id: a.account_code for a in accounts.values()}
    return {
        "transaction_id": t.transaction_id,
        "sender_account": reverse[t.sender_account_id],
        "receiver_account": reverse[t.receiver_account_id],
        "amount": str(t.amount),
        "currency": t.currency,
        "occurred_at": t.occurred_at.isoformat(),
        "status": t.status,
        "synthetic": True,
    }


def generate_batch(owner: UUID, tick: int, initialize: bool = False):
    """Runs in worker thread; single atomic DB commit per tick."""
    with _db_session() as db:
        existing_count = simulated_count(db, owner)
        if existing_count >= MAX_PER_OWNER:
            raise ValueError("Maximum synthetic transaction limit reached. Use Reset Demo Data to start again.")
        if initialize and existing_count:
            return []
        accounts = _seed_accounts(db, owner)
        rng = random.Random(uuid4().int)
        rows = []
        if initialize and not existing_count:
            # Populate a meaningful network immediately, not a decorative fake chart.
            candidates = [code for code, _ in SIM_CODES]
            for i in range(min(24, MAX_PER_OWNER-existing_count)):
                sender, receiver = rng.sample(candidates, 2)
                rows.append(_make_tx(owner, accounts, sender, receiver, rng.randrange(500, 80000), f"N_SEED{i}"))
        else:
            stage = tick % 12
            group = tick // 12
            if stage < 3:
                pairs = [("SYN_U01", "SYN_W01"), ("SYN_W01", "SYN_M01"), ("SYN_M01", "SYN_U01")]
                sender, receiver = pairs[stage]
                amount = [50000, 49500, 49000][stage]
                tag = f"C{group}_{stage}"
            elif stage < 6:
                pairs = [("SYN_U02", "SYN_B01"), ("SYN_B01", "SYN_W02"), ("SYN_W02", "SYN_M02")]
                sender, receiver = pairs[stage-3]
                amount = [35000, 34750, 34500][stage-3]
                tag = f"R{group}_{stage-3}"
            elif stage < 10:
                pairs = [("SYN_U03", "SYN_W03"), ("SYN_U04", "SYN_W03"), ("SYN_U05", "SYN_W03"), ("SYN_W03", "SYN_M03")]
                sender, receiver = pairs[stage-6]
                amount = [15000, 15000, 15000, 44000][stage-6]
                tag = f"M{group}_{stage-6}"
            else:
                sender, receiver = rng.sample([code for code, _ in SIM_CODES], 2)
                amount = rng.randrange(100, 125000)
                tag = "N"
            rows = [_make_tx(owner, accounts, sender, receiver, amount, tag)]
        db.add_all(rows)
        db.commit()
        return [_format_tx(t, accounts) for t in rows]


def reset_simulated_data(owner: UUID):
    with _db_session() as db:
        result = db.execute(delete(Transaction).where(
            Transaction.owner_id == owner,
            Transaction.transaction_id.like("FGSIM\\_%", escape="\\"),
        ))
        db.commit()
        return result.rowcount


def graph_snapshot(db: Session, owner: UUID, limit: int = 320):
    """Evidence is all persisted transactions; red edges are known simulator test scenarios only."""
    sender_a, receiver_a = aliased(Account), aliased(Account)
    records = db.execute(
        select(Transaction, sender_a.account_code, receiver_a.account_code)
        .join(sender_a, (Transaction.owner_id == sender_a.owner_id) & (Transaction.sender_account_id == sender_a.id))
        .join(receiver_a, (Transaction.owner_id == receiver_a.owner_id) & (Transaction.receiver_account_id == receiver_a.id))
        .where(Transaction.owner_id == owner)
        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(limit)
    ).all()
    nodes, edges, groups = {}, {}, defaultdict(list)
    recent = []
    for t, source, target in records:
        scenario = SCENARIO_RE.match(t.transaction_id)
        scenario_name = {"C": "circular", "R": "rapid", "M": "mule"}.get(scenario.group(1)) if scenario else None
        if scenario:
            groups[(scenario.group(1), scenario.group(2))].append((t, source, target, int(scenario.group(3))))
        for code in (source, target):
            if code not in nodes:
                part = code.split('_')
                kind = KIND_NAMES.get(part[1][0], 'account') if len(part) > 1 and code.startswith('SYN_') else 'account'
                nodes[code] = {"id": code, "label": code, "kind": kind, "incoming": 0, "outgoing": 0, "received": 0.0, "sent": 0.0, "synthetic": code.startswith("SYN_")}
        amount = float(t.amount)
        nodes[source]['outgoing'] += 1
        nodes[source]['sent'] += amount
        nodes[target]['incoming'] += 1
        nodes[target]['received'] += amount
        key = (source, target, scenario_name or "standard")
        if key not in edges:
            edges[key] = {"id": f"{source}>{target}:{scenario_name or 'standard'}", "source": source, "target": target,
                          "count": 0, "amount": 0.0, "scenario": scenario_name, "last_at": t.occurred_at.isoformat()}
        edges[key]['count'] += 1
        edges[key]['amount'] += amount
        if len(recent) < 14:
            recent.append({"id": t.transaction_id, "source": source, "target": target, "amount": amount,
                           "status": t.status, "at": t.occurred_at.isoformat(), "scenario": scenario_name})
    events = []
    for (code, group), items in groups.items():
        required = {"C": 3, "R": 3, "M": 4}[code]
        steps = {entry[3] for entry in items}
        if not set(range(required)).issubset(steps):
            continue
        ordered = sorted(items, key=lambda entry: entry[3])
        # Only label complete deliberately injected scenarios; this is NOT production fraud analysis.
        kind = {"C": "Circular transfer", "R": "Rapid movement", "M": "Potential mule pattern"}[code]
        created = max(entry[0].occurred_at for entry in ordered)
        events.append({"id": f"{code}{group}", "name": kind, "at": created.isoformat(), "severity": "high" if code == "C" else "medium",
                       "description": f"Controlled synthetic test pattern · {required} linked transactions",
                       "accounts": list(dict.fromkeys([entry[1] for entry in ordered] + [entry[2] for entry in ordered])),
                       "transaction_ids": [entry[0].transaction_id for entry in ordered]})
    events.sort(key=lambda event: event['at'], reverse=True)
    total = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.owner_id == owner)) or 0
    return {"nodes": list(nodes.values()), "edges": list(edges.values()), "transactions": recent,
            "scenarios": events[:30], "total_transactions": total, "window_count": len(records),
            "simulated_count": simulated_count(db, owner), "generated_at": utc_now().isoformat()}


class SimulationRunner:
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    def status(self, owner: UUID):
        state = self._jobs.get(str(owner))
        if not state:
            return {"running": False, "ticks": 0, "max_ticks": MAX_TICKS, "interval_seconds": 3, "error": None}
        return {key: value for key, value in state.items() if key in {"running", "ticks", "max_ticks", "interval_seconds", "error"}}

    async def start(self, owner: UUID, interval: int = 3):
        async with self._lock:
            key = str(owner)
            old = self._jobs.get(key)
            if old and old['running']:
                return self.status(owner)
            if not MIN_INTERVAL <= interval <= MAX_INTERVAL:
                raise HTTPException(422, detail="Interval must be between 2 and 10 seconds")
            count = await run_in_threadpool(self._get_count, owner)
            if count >= MAX_PER_OWNER:
                raise HTTPException(409, detail="Synthetic data cap reached. Reset demo transactions to continue.")
            stop = asyncio.Event()
            state = {"running": True, "ticks": 0, "max_ticks": MAX_TICKS, "interval_seconds": interval, "error": None, "stop": stop, "task": None, "offset": (uuid4().int % 100_000_000) * 12}
            self._jobs[key] = state
            state['task'] = asyncio.create_task(self._loop(owner, state), name=f"fraudgraph-simulator-{key}")
            return self.status(owner)

    @staticmethod
    def _get_count(owner):
        with _db_session() as db:
            return simulated_count(db, owner)

    async def _loop(self, owner, state):
        try:
            first = await run_in_threadpool(generate_batch, owner, 0, True)
            await sio.emit('simulation_transactions', {"transactions": first, "ticks": 0}, to=f"user:{owner}")
            for n in range(MAX_TICKS):
                try:
                    await asyncio.wait_for(state['stop'].wait(), timeout=state['interval_seconds'])
                    break
                except asyncio.TimeoutError:
                    pass
                if state['stop'].is_set():
                    break
                items = await run_in_threadpool(generate_batch, owner, state['offset'] + n, False)
                state['ticks'] = n + 1
                await sio.emit('simulation_transactions', {"transactions": items, "ticks": state['ticks']}, to=f"user:{owner}")
            state['running'] = False
        except asyncio.CancelledError:
            state['running'] = False
            raise
        except Exception as exc:
            # Never expose database internals to the browser.
            log.exception('Simulator failed for owner=%s', owner)
            state['running'] = False
            state['error'] = str(exc) if isinstance(exc, ValueError) else 'Simulator database error; check backend logs'
        finally:
            state['running'] = False
            await sio.emit('simulation_status', self.status(owner), to=f"user:{owner}")

    async def stop(self, owner: UUID):
        state = self._jobs.get(str(owner))
        if state and state['running']:
            state['stop'].set()
            await state['task']
        return self.status(owner)

    async def close(self):
        for state in list(self._jobs.values()):
            if state['running']:
                state['stop'].set()
        pending = [state['task'] for state in self._jobs.values() if state['task'] and not state['task'].done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


runner = SimulationRunner()
