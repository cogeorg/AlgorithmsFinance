"""The dashboard must agree with the raw results it displays."""

import statistics

import pytest
from data import (
    fmt_bytes, fmt_seconds, headline, load_memory, load_metadata, load_timing,
    memory_summary, noise_bound, ranges_separated, relative_to_first, revision_ratios, timing_summary,
)
from registry import VERSIONS


@pytest.fixture(scope="module")
def timing():
    return load_timing()


@pytest.fixture(scope="module")
def memory():
    return load_memory()


def test_saved_results_are_complete(timing, memory):
    n_pairs = sum(len(methods) for methods in VERSIONS.values())
    assert sorted(timing["version"].unique()) == sorted(VERSIONS)
    assert len(timing) == 15 * n_pairs * 5
    assert len(memory) == 15 * n_pairs * 3
    assert load_metadata("timing")["code"]["uncommitted_changes_in_src_or_bench"] is False
    assert load_metadata("memory")["code"]["uncommitted_changes_in_src_or_bench"] is False


def test_timing_summary_matches_raw_medians(timing):
    summary = timing_summary(timing)
    for _, row in summary.sample(20, random_state=0).iterrows():
        raw = timing[(timing["scenario"] == row["scenario"]) & (timing["version"] == row["version"])
                     & (timing["method"] == row["method"])]
        for col in ("prepare_s", "query_batch_s", "total_s"):
            assert row[f"{col}_median"] == pytest.approx(statistics.median(raw[col]))
            assert row[f"{col}_min"] == raw[col].min()
            assert row[f"{col}_max"] == raw[col].max()


def test_memory_summary_matches_raw(memory):
    summary = memory_summary(memory)
    row = summary[(summary["n"] == 100_000) & (summary["method"] == "hash")].iloc[0]
    raw = memory[(memory["scenario"] == row["scenario"]) & (memory["method"] == "hash")
                 & (memory["version"] == row["version"])]
    assert row["prepare_current_B"] == statistics.median(raw["prepare_current_B"])


@pytest.mark.parametrize("new,old,func", [("v2", "v1", "steps"), ("v3", "v2", "steps"), ("v3", "v1", "first")])
def test_ratios_are_new_over_old(timing, new, old, func):
    summary = timing_summary(timing)
    ratios = revision_ratios(summary) if func == "steps" else relative_to_first(summary)
    r = ratios[(ratios["scenario"] == 0) & (ratios["method"] == "binary") & (ratios["step"] == f"{new}/{old}")]
    s = summary[(summary["scenario"] == 0) & (summary["method"] == "binary")].set_index("version")
    assert len(r) == 1
    assert r.iloc[0]["query_batch_s_ratio"] == pytest.approx(
        s.loc[new, "query_batch_s_median"] / s.loc[old, "query_batch_s_median"])


def test_headline_matches_readme_claims(timing, memory):
    summary = timing_summary(timing)
    ratios = revision_ratios(summary)
    h = headline(summary, memory_summary(memory), ratios)
    assert set(h["steps"]) == {"v2/v1", "v3/v2"}
    assert h["noise"] == pytest.approx(noise_bound(ratios))

    # README: v2 is faster than v1 in all 15 scenarios, and the repeat ranges never overlap.
    *_, count, _, faster = h["steps"]["v2/v1"]
    assert faster == count == 15
    assert len(ranges_separated(summary, "v2", "v1")) == 15

    # README: v3 is faster than v2 in 14 of 15 scenarios (ranges separated in 11);
    # clearly for absent and mixed queries, not consistently when every query hits.
    low, _, count, _, faster = h["steps"]["v3/v2"]
    assert count == 15 and faster == 14 and low < 0
    assert len(ranges_separated(summary, "v3", "v2")) == 11
    r = ratios[(ratios["method"] == "binary") & (ratios["step"] == "v3/v2")]
    assert (r[r["hit_rate_target"] == 0.0]["query_batch_s_ratio"] < 0.87).all()  # 14-15 % faster
    assert (r[r["hit_rate_target"] == 0.5]["query_batch_s_ratio"] < 0.95).all()  # 6-10 % faster
    assert r[r["hit_rate_target"] == 1.0]["query_batch_s_ratio"].max() > 1.0  # one case slower
    assert h["fastest_q1"][0] == "linear"
    assert h["fastest_q100"][0] == "hash"
    assert 4.5 < h["hash_vs_sorted"] < 5.5


@pytest.mark.parametrize("value,text", [(2.5e-3, "2.5 ms"), (46e-9, "46 ns"), (1.2, "1.2 s")])
def test_fmt_seconds(value, text):
    assert fmt_seconds(value) == text


@pytest.mark.parametrize("value,text", [(920, "920 B"), (800_056, "781 KiB"), (4_194_520, "4 MiB")])
def test_fmt_bytes(value, text):
    assert fmt_bytes(value) == text
