"""Checks that the report never invents measurements or incomparable speedups."""
from copy import deepcopy
import unittest
import benchmark_report as report


def record(seconds=2.0, state="completed", phase="timing"):
    return dict(state=state, protocol={"machine": "A", "python": "same", "source": "same"},
        workload_sha256="input", summary=dict(phase=phase,event_count=100000,seed=42,scenario="case",
        replay_seconds=seconds,result_digest="a"*64,snapshot_digest="b"*64,
        fill_count=1,unfilled_qty_units=0,cancelled_qty_units=0,rejected_event_count=0,
        active_orders_peak=1,occupied_prices_peak=1,active_orders_final=0,occupied_prices_final=0))


class TestComparability(unittest.TestCase):
    def setUp(self):
        self.left,self.right=record(10),record(2)
        self.dl,self.dr=record(phase="diagnostics"),record(phase="diagnostics")

    def compare(self):
        return report.compare_pair(self.left,self.right,self.dl,self.dr)

    def test_complete_matching_groups_have_known_speedup(self):
        self.assertEqual(self.compare()["speedup"],5)

    def test_stopped_missing_or_partial_data_never_yields_speedup(self):
        self.left["state"]="stopped"
        self.left["summary"]["replay_seconds"]=None
        self.assertIsNone(self.compare()["speedup"])
        self.assertIsNone(report.compare_pair(None,self.right,self.dl,self.dr)["speedup"])

    def test_different_count_seed_or_input_is_incomparable(self):
        for field,value in (("event_count",10000),("seed",43)):
            candidate=deepcopy(self.left)
            candidate["summary"][field]=value
            self.assertIsNone(report.compare_pair(candidate,self.right,self.dl,self.dr)["speedup"])
        self.left["workload_sha256"]="different"
        self.assertIsNone(self.compare()["speedup"])

    def test_different_environment_or_protocol_is_incomparable(self):
        self.left["protocol"]["machine"]="B"
        self.assertEqual(self.compare()["status"],"incomparable")
        self.assertIsNone(self.compare()["speedup"])

    def test_missing_or_mismatched_diagnostics_blocks_speedup(self):
        self.dr["summary"]["snapshot_digest"]="c"*64
        self.assertEqual(self.compare()["status"],"mismatch")
        self.dr["state"]="stopped"
        self.assertIsNone(self.compare()["speedup"])
        self.dr["state"]="completed"
        self.dr["summary"]["snapshot_digest"]=None
        self.assertIsNone(self.compare()["speedup"])

    def test_memory_values_are_never_used_as_primary_speedup(self):
        self.left["summary"]["phase"]="memory"
        self.assertIsNone(self.compare()["speedup"])


class TestRecordedOutcomes(unittest.TestCase):
    def groups(self,completed):
        raw=[]
        for i in range(1,6):
            row=dict.fromkeys(report.METRICS)
            row.update(repetition=i,status="complete" if i<=completed else "stopped",
                       error=None if i<=completed else "Worker wall limit reached (60.000 seconds)")
            if i<=completed:row["replay_seconds"]=i
            raw.append(row)
        summary=dict.fromkeys(report.METRICS)
        summary.update(phase="timing",expected_repetitions=5,completed_repetitions=completed,
                       status="complete" if completed==5 else "incomplete")
        if completed==5:summary["replay_seconds"]=3
        return summary,raw

    def test_complete_group_median_is_verified(self):
        summary,raw=self.groups(5)
        self.assertEqual(report.classify(summary,raw,10),"completed")
        summary["replay_seconds"]=99
        with self.assertRaises(AssertionError):report.classify(summary,raw,10)

    def test_documented_timeout_is_coverage_but_not_completion(self):
        summary,raw=self.groups(2)
        self.assertEqual(report.classify(summary,raw,60.1),"stopped")
        self.assertIsNone(summary["replay_seconds"])
        with self.assertRaises(AssertionError):report.classify(summary,raw,None)

    def test_fabricated_median_from_partial_repetitions_is_rejected(self):
        summary,raw=self.groups(2)
        summary["replay_seconds"]=1.5
        with self.assertRaises(AssertionError):report.classify(summary,raw,60.1)

    def test_unattempted_group_is_distinct_from_stopped(self):
        summary,raw=self.groups(0)
        for r in raw:r.update(status="not_run",error="Campaign wall deadline reached")
        self.assertEqual(report.classify(summary,raw,None),"unattempted")


if __name__=="__main__":
    unittest.main()

