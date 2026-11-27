"""Public measured pipeline; sequential batch failures are local to an asset."""
from dataclasses import dataclass
from pathlib import Path
from .data import load_calibrate,first_exercise


@dataclass
class Analysis:
    window: object
    result: object
    exercise: dict


def analyze(path,window,version='B'):
    from . import METHODS
    w=load_calibrate(path,window)
    key={'A':('baseline','A'),'B':('fast','B')}[version]
    result=METHODS[key](*w.params)
    exercise=first_exercise(w.prices,w.timestamps,result.boundary,w.params[1])
    return Analysis(w,result,exercise)


def summarize(path,window,analysis):
    w=analysis.window
    return dict(symbol=Path(path).stem,window=window,status='ok',error='',N=w.params[-1],
                first_utc=w.timestamps[0],last_utc=w.timestamps[-1],T=w.T,s=w.s,
                S0=w.params[0],K=w.params[1],u=w.params[2],d=w.params[3],R=w.params[4],
                value=analysis.result.value,exercise_t=analysis.exercise['t'],
                exercise_utc=analysis.exercise['timestamp_utc'],payoff=analysis.exercise['payoff'],
                near_tie_layers=sum(analysis.result.near_ties))


def analyze_many(paths,window,version='B'):
    rows=[]
    for path in paths:
        try:
            analysis=analyze(path,window,version)
            rows.append(summarize(path,window,analysis))
            del analysis
        except (ValueError,OverflowError,OSError) as exc:
            rows.append(dict(symbol=Path(path).stem,window=window,status='error',error=str(exc),N=None))
    return rows
