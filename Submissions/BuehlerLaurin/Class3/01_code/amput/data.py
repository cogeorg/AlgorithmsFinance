"""Read-only observed-row windows, calibration and exercise reporting."""
import csv
import math
import statistics
from datetime import datetime
from dataclasses import dataclass


@dataclass
class Window:
    prices: list
    timestamps: list
    params: tuple
    s: float
    T: float


def load_calibrate(path,window):
    if window not in ('1y','5y'):
        raise ValueError('window must be 1y or 5y')
    prices=[]; timestamps=[]; dates=[]
    with open(path,newline='',encoding='utf-8') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames != ['timestamp_utc','close']:
            raise ValueError('Expected timestamp_utc,close columns')
        for row in reader:
            p=float(row['close'])
            t=datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))
            if not math.isfinite(p) or p<=0 or t.utcoffset() is None or t.utcoffset().total_seconds()!=0:
                raise ValueError('Require positive finite closes and UTC timestamps')
            if dates and t<=dates[-1]:
                raise ValueError('Timestamps must increase strictly')
            prices.append(p); timestamps.append(row['timestamp_utc']); dates.append(t)
    if window=='1y':
        if len(prices)<8761:
            raise ValueError('One year requires at least 8761 observed closes')
        prices=prices[-8761:]; timestamps=timestamps[-8761:]; dates=dates[-8761:]
    if len(prices)<3:
        raise ValueError('Calibration needs at least three closes')
    n=len(prices)-1
    returns=[math.log(b/a) for a,b in zip(prices,prices[1:])]
    s=statistics.stdev(returns)
    T=(dates[-1]-dates[0]).total_seconds()/(365.25*86400)
    u=math.exp(s); d=1/u; R=math.exp(.04*T/n)
    from .common import validate
    validate(prices[0],prices[0],u,d,R,n)
    return Window(prices,timestamps,(prices[0],prices[0],u,d,R,n),s,T)


def first_exercise(prices,timestamps,boundary,K):
    if not len(prices)==len(timestamps)==len(boundary):
        raise ValueError('Path, timestamps and boundary lengths differ')
    for t,(p,b) in enumerate(zip(prices,boundary)):
        if b is not None and p<=b:
            return dict(t=t,timestamp_utc=timestamps[t],payoff=K-p)
    return dict(t=None,timestamp_utc=None,payoff=None)
