"""Exercise saved-data dashboard widgets and render paths without running benchmarks."""
import json
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"/"phase1_final"

def widget(items,label):
    return next(w for w in items if w.label==label)

def check(app,label):
    assert not app.exception,[e.message for e in app.exception]
    figures=len(app.get("image"))
    assert figures>0,(label,"No rendered Matplotlib figures")
    return dict(case=label,figures=figures,tables=len(app.dataframe),
                metrics={m.label:m.value for m in app.metric})

def run():
    evidence=[]
    with patch("benchmark.campaign",side_effect=AssertionError("Dashboard must never execute benchmarks")):
        app=AppTest.from_file(str(ROOT/"dashboard.py"),default_timeout=60).run()
        evidence.append(check(app,"default replay"))
        for experiment in ("replay","market-sell","queue-concentration","cancel-churn"):
            widget(app.sidebar.selectbox,"Experiment").set_value(experiment).run()
            widget(app.sidebar.multiselect,"Requested counts").set_value([1000])
            widget(app.sidebar.multiselect,"Seeds").set_value([42]).run()
            evidence.append(check(app,experiment+" count1000 seed42"))
        widget(app.sidebar.selectbox,"Experiment").set_value("replay").run()
        widget(app.sidebar.selectbox,"Scenario").set_value("buildup")
        widget(app.sidebar.multiselect,"Requested counts").set_value([100000])
        widget(app.sidebar.multiselect,"Seeds").set_value([42])
        widget(app.sidebar.multiselect,"Implementations").set_value(["baseline"]).run()
        evidence.append(check(app,"documented Baseline large-book stops"))
        assert any(m.label=="Stopped groups" and int(m.value)>0 for m in app.metric)
        widget(app.sidebar.selectbox,"Scenario").set_value("sweep")
        widget(app.sidebar.multiselect,"Requested counts").set_value([10000])
        widget(app.checkbox,"Show saved raw repetitions (including partial groups)").set_value(True).run()
        evidence.append(check(app,"retained partial memory repetitions"))
        raw=next(d.value for d in app.dataframe if {"repetition","status","source"}.issubset(d.value.columns))
        memory=raw[raw["phase"]=="memory"]
        assert any(memory["status"]=="complete") and any(memory["status"]!="complete")
        widget(app.sidebar.selectbox,"Scenario").set_value("buildup")
        widget(app.sidebar.multiselect,"Requested counts").set_value([100000])
        widget(app.sidebar.multiselect,"Implementations").set_value(["revised"]).run()
        evidence.append(check(app,"unpaired Revised completed large-book observations"))
        widget(app.sidebar.multiselect,"Implementations").set_value(["baseline","revised"])
        widget(app.sidebar.checkbox,"Comparable pairs only in plots").set_value(False).run()
        evidence.append(check(app,"independent completed curves with pair restriction disabled"))
        widget(app.sidebar.selectbox,"Experiment").set_value("queue-concentration").run()
        widget(app.sidebar.multiselect,"Requested counts").set_value([1000])
        widget(app.sidebar.multiselect,"Price-level setting").set_value([4]).run()
        evidence.append(check(app,"four-level queue filter"))
        widget(app.sidebar.selectbox,"Experiment").set_value("market-sell").run()
        widget(app.sidebar.multiselect,"Requested counts").set_value([1000])
        widget(app.sidebar.multiselect,"Sale percentage").set_value([200]).run()
        evidence.append(check(app,"oversized-sale filter"))
        captions=" ".join(c.value for c in app.caption)
        assert "10^-8 BTC" in captions and "nearest rank" in captions
    result=dict(status="passed",saved_data_only=True,cases=evidence,
        boundaries="AppTest renders every tab, checks plots/tables, filters, units and documented stops. Browser screenshot and HTTP health recorded separately.")
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"dashboard_tests.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))
    return result

if __name__=="__main__":run()
