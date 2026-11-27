"""Tests for deterministic synthetic benchmark input generation."""

from __future__ import annotations

from itertools import product

import pytest

from algorithms_finance.data_01_generation import (
    DEFAULT_ABSENT_POLICY,
    DEFAULT_ARRAY_PROFILE,
    GENERATOR_VERSION,
    MANDATORY_ARRAY_SIZES,
    MANDATORY_QUERY_COUNTS,
    MANDATORY_SCENARIOS,
    generate_case,
    make_configuration,
    mandatory_configurations,
)


MANDATORY_CONFIGS = mandatory_configurations()


def test_mandatory_matrix_contains_exactly_eighteen_configurations() -> None:
    expected = set(
        product(
            MANDATORY_ARRAY_SIZES,
            MANDATORY_QUERY_COUNTS,
            MANDATORY_SCENARIOS,
        )
    )
    actual = {
        (config.array_size, config.query_count, config.scenario)
        for config in MANDATORY_CONFIGS
    }

    assert len(MANDATORY_CONFIGS) == 18
    assert len({config.case_id for config in MANDATORY_CONFIGS}) == 18
    assert actual == expected
    assert all(
        config.dataset_class == "mandatory_benchmark"
        for config in MANDATORY_CONFIGS
    )
    assert all(
        config.array_profile == DEFAULT_ARRAY_PROFILE
        for config in MANDATORY_CONFIGS
    )
    assert all(
        config.absent_policy == DEFAULT_ABSENT_POLICY
        for config in MANDATORY_CONFIGS
    )


@pytest.mark.parametrize("config", MANDATORY_CONFIGS, ids=lambda item: item.case_id)
def test_mandatory_case_values_and_metadata(config) -> None:
    case = generate_case(config)
    array_values = set(case.array)
    metadata = case.metadata
    hits = [query in array_values for query in case.queries]

    assert len(case.array) == config.array_size
    assert len(case.queries) == config.query_count
    assert metadata["dataset_class"] == "mandatory_benchmark"
    assert metadata["generator_version"] == GENERATOR_VERSION
    assert metadata["array_seed"] == config.array_seed
    assert metadata["query_seed"] == config.query_seed
    assert metadata["hit_count"] == sum(hits)
    assert metadata["actual_hit_rate"] == sum(hits) / len(hits)
    assert metadata["unique_count"] == len(array_values)
    assert metadata["duplicate_count"] == len(case.array) - len(array_values)
    assert metadata["duplicate_rate"] == (
        metadata["duplicate_count"] / len(case.array)
    )
    assert len(metadata["array_fingerprint_sha256"]) == 64
    assert len(metadata["query_fingerprint_sha256"]) == 64
    assert metadata["python_version"]
    assert metadata["python_implementation"]
    assert metadata["platform"]

    if config.scenario == "all_present":
        assert all(hits)
        assert metadata["actual_hit_rate"] == 1.0
    elif config.scenario == "all_absent":
        assert not any(hits)
        assert metadata["actual_hit_rate"] == 0.0
    elif config.query_count == 100:
        assert sum(hits) == 50
        assert metadata["actual_hit_rate"] == 0.5
        assert metadata["is_true_mixed_batch"] is True
    else:
        expected_hits = 1 if config.query_seed % 2 == 0 else 0
        assert sum(hits) == expected_hits
        assert metadata["target_hit_rate"] == 0.5
        assert metadata["actual_hit_rate"] == float(expected_hits)
        assert metadata["is_true_mixed_batch"] is False
        assert metadata["mixed_singleton_policy"] == (
            "present_if_query_seed_even"
        )

    absent_queries = [
        query for query, is_present in zip(case.queries, hits) if not is_present
    ]
    assert all(0 <= query < 10 * config.array_size for query in absent_queries)


def test_generation_is_reproducible_for_identical_configuration() -> None:
    config = make_configuration(
        1_000,
        100,
        "mixed",
        dataset_class="mandatory_benchmark",
    )

    first = generate_case(config)
    second = generate_case(config)

    assert first.array == second.array
    assert first.queries == second.queries
    assert first.metadata == second.metadata


@pytest.mark.parametrize("array_size", MANDATORY_ARRAY_SIZES)
def test_same_array_size_reuses_identical_mandatory_array(array_size: int) -> None:
    configs = [
        config for config in MANDATORY_CONFIGS if config.array_size == array_size
    ]
    cases = [generate_case(config) for config in configs]

    assert len({config.array_seed for config in configs}) == 1
    assert len(
        {case.metadata["array_fingerprint_sha256"] for case in cases}
    ) == 1


def test_mandatory_query_seeds_are_unique() -> None:
    assert len({config.query_seed for config in MANDATORY_CONFIGS}) == 18


@pytest.mark.parametrize(
    ("profile", "expected_duplicate_count"),
    (
        ("all_unique", 0),
        ("all_identical", 999),
    ),
)
def test_exact_duplicate_stress_profiles(
    profile: str,
    expected_duplicate_count: int,
) -> None:
    config = make_configuration(
        1_000,
        100,
        "all_present",
        dataset_class="optional_stress",
        array_profile=profile,
    )
    case = generate_case(config)

    assert case.metadata["dataset_class"] == "optional_stress"
    assert case.metadata["duplicate_count"] == expected_duplicate_count


def test_high_duplicate_stress_profile_uses_small_value_pool() -> None:
    config = make_configuration(
        1_000,
        100,
        "all_present",
        dataset_class="optional_stress",
        array_profile="high_duplicate",
    )
    case = generate_case(config)

    assert case.metadata["dataset_class"] == "optional_stress"
    assert case.metadata["unique_count"] <= 10
    assert case.metadata["duplicate_rate"] >= 0.99


def test_outside_range_absent_stress_is_balanced() -> None:
    config = make_configuration(
        1_000,
        100,
        "all_absent",
        dataset_class="optional_stress",
        absent_policy="outside_range_balanced",
    )
    case = generate_case(config)
    upper_bound = 10 * config.array_size

    below = [query for query in case.queries if query < 0]
    above = [query for query in case.queries if query >= upper_bound]

    assert len(below) == 50
    assert len(above) == 50
    assert not any(query in set(case.array) for query in case.queries)
    assert case.metadata["actual_hit_rate"] == 0.0
