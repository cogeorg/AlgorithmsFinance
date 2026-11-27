"""Synthetic-data generator: deterministic, exact hit counts, identical arrays."""
import pytest

from datagen.generator import SCENARIOS, DatasetSpec, generate


def spec(**kw):
    base = dict(n=1000, q=100, scenario="mixed", seed=2026)
    base.update(kw)
    return DatasetSpec(**base)


def test_deterministic_for_same_spec():
    a, b = generate(spec()), generate(spec())
    assert a.ids == b.ids and a.queries == b.queries
    assert a.ids_sha256 == b.ids_sha256 and a.queries_sha256 == b.queries_sha256


def test_different_seed_changes_data():
    assert generate(spec(seed=1)).ids != generate(spec(seed=2)).ids


def test_same_array_for_every_q_and_scenario():
    arrays = {tuple(generate(spec(q=q, scenario=s)).ids)
              for q in (1, 100) for s in SCENARIOS}
    assert len(arrays) == 1


@pytest.mark.parametrize("n, q", [(0, 0), (1, 1), (1000, 1), (1000, 100), (10, 37)])
def test_sizes(n, q):
    scenario = "all_absent" if n == 0 else "mixed"
    d = generate(spec(n=n, q=q, scenario=scenario))
    assert len(d.ids) == n and len(d.queries) == q


def test_all_present():
    d = generate(spec(scenario="all_present"))
    present = set(d.ids)
    assert all(x in present for x in d.queries)
    assert d.present_queries == 100 and d.realized_hit_rate == 1.0


def test_all_absent():
    d = generate(spec(scenario="all_absent"))
    present = set(d.ids)
    assert not any(x in present for x in d.queries)
    assert d.present_queries == 0 and d.realized_hit_rate == 0.0


def test_mixed_has_exact_hit_count():
    d = generate(spec(scenario="mixed", q=100))
    present = set(d.ids)
    assert sum(x in present for x in d.queries) == d.present_queries == 50
    assert d.realized_hit_rate == 0.5


def test_mixed_single_query_rounds_half_up():
    # q=1 with target 0.5 cannot be mixed; documented: rounds half up to 1 hit.
    d = generate(spec(scenario="mixed", q=1))
    assert d.present_queries == 1 and d.realized_hit_rate == 1.0


def test_unique_policy_has_no_duplicates():
    d = generate(spec(duplicate_policy="unique"))
    assert len(set(d.ids)) == len(d.ids) == d.distinct_values


def test_allow_policy_produces_duplicates():
    d = generate(spec(duplicate_policy="allow"))
    assert d.distinct_values < len(d.ids)


def test_ids_are_python_ints_in_id_space():
    d = generate(spec())
    assert all(type(x) is int for x in d.ids + d.queries)
    assert all(0 <= x < d.spec.id_space for x in d.ids)


def test_empty_array_all_absent_queries():
    d = generate(spec(n=0, q=5, scenario="all_absent"))
    assert d.ids == [] and len(d.queries) == 5


@pytest.mark.parametrize("kw", [
    dict(n=0, q=5, scenario="all_present"),   # no IDs to hit
    dict(n=-1),
    dict(q=-1),
    dict(scenario="sometimes"),
    dict(duplicate_policy="maybe"),
    dict(id_space_factor=1),                  # could leave no absent IDs
])
def test_invalid_specs_rejected(kw):
    with pytest.raises(ValueError):
        generate(spec(**kw))


def test_summary_has_dataset_columns():
    row = generate(spec()).summary()
    for col in ["dataset_id", "n", "q", "scenario", "target_hit_rate", "present_queries",
                "realized_hit_rate", "mean_first_hit_frac", "duplicate_policy", "id_space",
                "distinct_values", "seed", "array_sha256", "queries_sha256"]:
        assert col in row


def test_golden_checksums():
    # Regression guard: the published datasets must be regenerated bit for bit.
    # If this fails on another Python version, random's algorithms changed; compare
    # the checksums in 02_results/<run_id>/datasets.csv before trusting a comparison.
    d = generate(spec(n=1000, q=100, scenario="mixed", seed=2026))
    assert d.ids_sha256 == "ad8fd7ff5d17431a6f6a36da60e9d4c2e475a4777a6edd0b8a5b5101aeb9a813"
    assert d.queries_sha256 == "919ea6783eacb1203e89a29cc827c3e8c54447d38248786eb72cdcec9d656513"


def test_query_order_is_shuffled():
    d = generate(spec(scenario="mixed", q=100))
    present = set(d.ids)
    flags = [x in present for x in d.queries]
    assert flags != sorted(flags, reverse=True)  # hits are not simply listed first


@pytest.mark.parametrize("n", [1000, 10_000, 100_000])
@pytest.mark.parametrize("q", [1, 100])
def test_hits_are_found_mid_array_on_average(n, q):
    # Stratified first occurrences: a linear scan finds hits after about n/2 on
    # average, for every n and q, so linear-search scaling is not distorted.
    d = generate(spec(n=n, q=q, scenario="all_present"))
    assert 0.45 <= d.mean_first_hit_frac <= 0.55


def test_mean_first_hit_frac_counts_first_occurrence():
    from datagen.generator import Dataset
    d = Dataset(spec(n=4, q=2, scenario="all_present"), ids=[5, 6, 5, 7], queries=[5, 7],
                present_queries=2)
    assert d.mean_first_hit_frac == (0 + 3) / 2 / 4
    assert generate(spec(n=10, q=3, scenario="all_absent")).mean_first_hit_frac is None
