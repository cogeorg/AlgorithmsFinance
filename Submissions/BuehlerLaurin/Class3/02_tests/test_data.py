import math
import pytest
from amput.data import load_calibrate, first_exercise


def test_tiny_hand_csv(tmp_path):
    path = tmp_path/'tiny.csv'
    path.write_text('timestamp_utc,close\n2026-01-01T00:00:00Z,100\n2026-01-01T01:00:00Z,110\n2026-01-01T03:00:00Z,99\n',encoding='utf-8')
    result = load_calibrate(path,'5y')
    s = abs(math.log(1.1)-math.log(.9))/math.sqrt(2)
    assert result.s == pytest.approx(s,abs=1e-15)
    assert result.T == pytest.approx(3/(365.25*24),abs=1e-15)
    assert result.params == pytest.approx((100,100,math.exp(s),math.exp(-s),math.exp(.04*result.T/2),2))
    assert result.timestamps[-1] == '2026-01-01T03:00:00Z'


def test_first_exercise_hit_and_never():
    assert first_exercise([100,80,90],['a','b','c'],[None,85,95],100) == {'t':1,'timestamp_utc':'b','payoff':20}
    assert first_exercise([100,90],['a','b'],[None,85],100) == {'t':None,'timestamp_utc':None,'payoff':None}


@pytest.mark.parametrize('prices',['100\n100\n100','100\n101','100\n0\n99','100\nnan\n99'])
def test_invalid_calibration(tmp_path,prices):
    path=tmp_path/'bad.csv'
    lines=prices.splitlines()
    path.write_text('timestamp_utc,close\n'+''.join(f'2026-01-01T0{i}:00:00Z,{p}\n' for i,p in enumerate(lines)),encoding='utf-8')
    with pytest.raises(ValueError):
        load_calibrate(path,'5y')


def test_last_rows_not_calendar(tmp_path):
    from datetime import datetime,timedelta,timezone
    path=tmp_path/'rows.csv'
    start=datetime(2023,1,1,tzinfo=timezone.utc)
    with path.open('w',encoding='utf-8') as f:
        f.write('timestamp_utc,close\n')
        for i in range(8765):
            f.write(f'{(start+timedelta(hours=2*i)).isoformat()},{100+i%3}\n')
    result=load_calibrate(path,'1y')
    assert result.params[-1] == 8760
    assert result.prices[0] == 101
    assert result.T == pytest.approx(17520/(365.25*24))
