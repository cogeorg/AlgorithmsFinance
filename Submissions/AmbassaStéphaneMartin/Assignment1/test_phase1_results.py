"""Independent final reporting cases and a saved-data-only dashboard smoke check."""
from copy import deepcopy
import unittest
from phase1_results import identity,sale_oracle,diagnostic_pair,nonprice_signature
from dashboard import comparable_phase
from benchmark_report import ROOT,saved_path
from benchmark_report import compare_pair

class TestFinalResults(unittest.TestCase):
    def test_comparison_boundary_rejects_sale_and_level_variants(self):
        left=dict(state="completed",protocol={},workload_sha256="same",summary=dict(phase="timing",experiment="market-sell",
            requested_count=1000,event_count=1001,seed=42,scenario="controlled_bids",levels=1000,sale_percent=10))
        for field,value in (("experiment","queue-concentration"),("levels",4),("sale_percent",100),("requested_count",10000)):
            other=deepcopy(left);other["summary"][field]=value
            self.assertEqual(compare_pair(left,other)["status"],"incomparable")

    def test_diagnostics_checked_without_primary_timing(self):
        base=dict(experiment="replay",scenario="buildup",requested_count=1000,event_count=1000,seed=42,levels=1000,
            sale_percent=None,phase="diagnostics",version="baseline",state="completed",protocol={},
            workload_sha256="input",result_digest="ordered",snapshot_digest="book",fill_count=3,price_levels_visited=None)
        other=dict(base,version="revised")
        self.assertEqual(diagnostic_pair(base,other)["status"],"matching")
        other["fill_count"]=4
        self.assertEqual(diagnostic_pair(base,other)["status"],"mismatch")
        other["state"]="stopped"
        self.assertEqual(diagnostic_pair(base,other)["status"],"unavailable")

    def test_concentration_holds_nonprice_fields_fixed(self):
        a=self.orders();b=deepcopy(a)
        for e in b:e["price_ticks"]=500
        self.assertEqual(nonprice_signature(a),nonprice_signature(b))
        b[0]["qty_units"]+=1
        self.assertNotEqual(nonprice_signature(a),nonprice_signature(b))

    def test_archived_paths_are_rebased_without_editing_manifests(self):
        self.assertEqual(saved_path(r"C:\old\checkout\Assignment1\data\benchmark\sample.jsonl.gz"),ROOT/"data"/"benchmark"/"sample.jsonl.gz")
        self.assertEqual(saved_path(r"C:\old\checkout\Assignment1\results\run\workers\checkpoint.json"),ROOT/"results"/"run"/"workers"/"checkpoint.json")
        self.assertEqual(saved_path(r"results\run\raw.jsonl"),ROOT/"results"/"run"/"raw.jsonl")
    def orders(self):
        return [dict(seq=i,event_id=f"e{i}",order_id=f"b{i}",side="BUY",type="LIMIT",price_ticks=p,qty_units=q)
                for i,p,q in ((1,100,2),(2,100,1),(3,99,7),(4,98,20))]
    def test_literal_sale_counts_and_residuals(self):
        for pct,quantity,fills,levels,residual in ((10,3,2,1,0),(100,30,4,3,0),(200,60,4,3,30)):
            with self.subTest(pct=pct):
                r=sale_oracle(self.orders(),pct)
                self.assertEqual((r["requested_sale_qty_units"],r["fill_count"],r["price_levels_visited"],r["unfilled_qty_units"]),
                                 (quantity,fills,levels,residual))
    def test_full_identity_preserves_variants(self):
        r=dict(experiment="market-sell",scenario="controlled_bids",requested_count=1000,event_count=1001,
               seed=42,levels=1000,sale_percent=10,version="baseline",phase="timing")
        for key,value in (("sale_percent",100),("levels",4),("experiment","queue-concentration"),
                          ("phase","memory"),("seed",43),("version","revised")):
            other=deepcopy(r);other[key]=value
            self.assertNotEqual(identity(r),identity(other))
    def test_integer_fraction_above_float_precision(self):
        events=self.orders();events[0]["qty_units"]=10**30+1
        r=sale_oracle(events,10)
        self.assertIs(type(r["requested_sale_qty_units"]),int)
        self.assertEqual(r["requested_sale_qty_units"],10**29+3)
    def test_incomplete_phase_not_compared(self):
        base=dict(experiment="replay",scenario="buildup",requested_count=1000,event_count=1000,seed=42,levels=1000,
                  sale_percent=None,case_id="x",phase="memory",version="baseline",state="stopped",protocol={})
        revised=dict(base,version="revised",state="completed")
        comparison=[dict(case_id="x",seed=42,levels=1000,sale_percent=None,status="comparable")]
        self.assertEqual(comparable_phase([base,revised],comparison,"memory"),[])

if __name__=="__main__":unittest.main()

