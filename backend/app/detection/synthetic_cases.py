from datetime import datetime,timedelta,timezone
import random
KINDS = ('ordinary','payroll','collections','legitimate_fast_chain','legitimate_settlement','legitimate_circular','circular','rapid','mule')
FRAUD=set(KINDS[-3:])

def make_case(kind,index,rng):
    # Distinct account and reference IDs are deliberately not predictive inputs.
    origin=datetime(2026,8,1,tzinfo=timezone.utc)+timedelta(days=index%65,minutes=(index*7)%1440)
    prefix=f'T{index:07d}'
    rows=[]
    def add(src,dst,amount,seconds):
        rows.append({'id':f'{prefix}_{len(rows):02d}', 'source':f'{prefix}_{src}', 'target':f'{prefix}_{dst}', 'amount':round(max(50,amount),2), 'at':origin+timedelta(seconds=seconds)})
    base=rng.uniform(2500, 98000)
    def gaps(n,fast=False):
        return [rng.uniform(14,600 if fast else 1500) for _ in range(n)]
    if kind=='ordinary':
        t=0
        for j in range(rng.randint(4,9)):
            add(f'A{j}',f'B{j}',base*rng.uniform(.15,1.6),t);t+=rng.uniform(300,8200)
    elif kind=='payroll':
        t=0
        for j in range(rng.randint(4,10)):
            add('PAY',f'EMP{j}',rng.uniform(10000,125000),t);t+=rng.uniform(5,40)
    elif kind=='collections':
        t=0
        for j in range(rng.randint(4,8)):
            add(f'BUY{j}','SHOP',rng.uniform(300,82000),t);t+=rng.uniform(12,125)
    elif kind in ('legitimate_fast_chain','rapid'):
        fraud = (kind=='rapid'); confusing = rng.random() < (.25 if fraud else .30)
        aggressive=fraud if not confusing else not fraud
        n=rng.choice([3,3,3,4]);t=0
        decay=rng.uniform(.69,.97) if aggressive else rng.uniform(.90,1.02)
        for j in range(n):
            add(f'C{j}',f'C{j+1}',base*(decay**j)*rng.uniform(.97,1.03),t)
            t+=rng.uniform(15,650) if aggressive else rng.uniform(25,900)
    elif kind in ('legitimate_circular','circular'):
        fraud=kind=='circular'; confusing=rng.random() < (.26 if fraud else .30)
        aggressive=fraud if not confusing else not fraud
        n=rng.choice([3,3,3,4]);t=0
        decay=rng.uniform(.7,.96) if aggressive else rng.uniform(.88,1.015)
        for j in range(n):
            add(f'C{j}',f'C{(j+1)%n}',base*(decay**j)*rng.uniform(.97,1.03),t)
            t+=rng.uniform(20,700) if aggressive else rng.uniform(20,840)
    elif kind in ('legitimate_settlement','mule'):
        fraud=kind=='mule'; confusing=rng.random() < (.25 if fraud else .30)
        aggressive=fraud if not confusing else not fraud
        n=rng.choice([3,3,3,4,5]);t=0
        contributions=[]
        for j in range(n):
            amount=rng.uniform(2000,45000)
            contributions.append(amount)
            add(f'FEED{j}','HUB',amount,t)
            t+=rng.uniform(12,350) if aggressive else rng.uniform(20,420)
        fraction=rng.uniform(.51,1.18) if aggressive else rng.uniform(.80,1.1)
        add('HUB','PAYOUT',sum(contributions)*fraction,t+rng.uniform(15,720))
    else:raise ValueError(kind)
    return rows

def generate(seed,per_kind=40,offset=0):
    rng=random.Random(seed);kinds=[name for name in KINDS for _ in range(per_kind)];rng.shuffle(kinds)
    return [(make_case(k,index+offset,rng),int(k in FRAUD),k) for index,k in enumerate(kinds)]
