"""Deterministic synthetic inputs for the membership-search laboratory.

This module is intentionally independent of algorithm implementations,
benchmark timing, memory tracing, and dashboard code. It creates input arrays,
ordered query batches, and reproducibility metadata only.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import platform
import random
import sys
from typing import Any, Final


GENERATOR_VERSION: Final = "1.0.0"
SEED_SCHEMA_VERSION: Final = 1
BASE_SEED: Final = 2026

MANDATORY_ARRAY_SIZES: Final = (1_000, 10_000, 100_000)
MANDATORY_QUERY_COUNTS: Final = (1, 100)
MANDATORY_SCENARIOS: Final = ("all_present", "all_absent", "mixed")

DEFAULT_ARRAY_PROFILE: Final = "sampling_with_replacement"
DEFAULT_ABSENT_POLICY: Final = "within_range_gap"
ID_RANGE_MULTIPLIER: Final = 10

ARRAY_PROFILES: Final = (
    DEFAULT_ARRAY_PROFILE,
    "all_unique",
    "all_identical",
    "high_duplicate",
)
ABSENT_POLICIES: Final = (
    DEFAULT_ABSENT_POLICY,
    "outside_range_balanced",
)
DATASET_CLASSES: Final = ("mandatory_benchmark", "optional_stress")

_SCENARIO_CODE: Final = {
    "all_present": 1,
    "all_absent": 2,
    "mixed": 3,
}
_ARRAY_PROFILE_CODE: Final = {
    "sampling_with_replacement": 1,
    "all_unique": 2,
    "all_identical": 3,
    "high_duplicate": 4,
}
_ABSENT_POLICY_CODE: Final = {
    "within_range_gap": 1,
    "outside_range_balanced": 2,
}
_DATASET_CLASS_CODE: Final = {
    "mandatory_benchmark": 1,
    "optional_stress": 2,
}


@dataclass(frozen=True)
class SyntheticConfig:
    """Complete, explicit configuration for one generated query batch."""

    case_id: str
    dataset_class: str
    array_size: int
    query_count: int
    scenario: str
    array_profile: str
    absent_policy: str
    array_seed: int
    query_seed: int
    id_range_multiplier: int = ID_RANGE_MULTIPLIER


@dataclass(frozen=True)
class SyntheticCase:
    """Generated values and the metadata required to reproduce them."""

    array: list[int]
    queries: list[int]
    metadata: dict[str, Any]


def _size_code(array_size: int) -> int:
    """Return a stable code without using Python's process-randomized hash."""

    try:
        return MANDATORY_ARRAY_SIZES.index(array_size) + 1
    except ValueError:
        return array_size


def _query_count_code(query_count: int) -> int:
    try:
        return MANDATORY_QUERY_COUNTS.index(query_count) + 1
    except ValueError:
        return query_count


def _derive_array_seed(
    array_size: int,
    array_profile: str,
    dataset_class: str,
) -> int:
    namespace = BASE_SEED * 1_000_000 + SEED_SCHEMA_VERSION * 100_000
    return (
        namespace
        + _DATASET_CLASS_CODE[dataset_class] * 10_000
        + _ARRAY_PROFILE_CODE[array_profile] * 1_000
        + _size_code(array_size)
    )


def _derive_query_seed(
    array_size: int,
    query_count: int,
    scenario: str,
    array_profile: str,
    absent_policy: str,
    dataset_class: str,
) -> int:
    namespace = BASE_SEED * 1_000_000 + SEED_SCHEMA_VERSION * 100_000
    return (
        namespace
        + 50_000
        + _DATASET_CLASS_CODE[dataset_class] * 1_000_000
        + _ARRAY_PROFILE_CODE[array_profile] * 100_000
        + _ABSENT_POLICY_CODE[absent_policy] * 10_000
        + _size_code(array_size) * 101
        + _query_count_code(query_count) * 10
        + _SCENARIO_CODE[scenario]
    )


def make_configuration(
    array_size: int,
    query_count: int,
    scenario: str,
    *,
    dataset_class: str = "optional_stress",
    array_profile: str = DEFAULT_ARRAY_PROFILE,
    absent_policy: str = DEFAULT_ABSENT_POLICY,
) -> SyntheticConfig:
    """Build a validated configuration with explicit deterministic seeds."""

    if array_size <= 0:
        raise ValueError("array_size must be a positive integer")
    if query_count <= 0:
        raise ValueError("query_count must be a positive integer")
    if scenario not in MANDATORY_SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario}")
    if dataset_class not in DATASET_CLASSES:
        raise ValueError(f"unsupported dataset_class: {dataset_class}")
    if array_profile not in ARRAY_PROFILES:
        raise ValueError(f"unsupported array_profile: {array_profile}")
    if absent_policy not in ABSENT_POLICIES:
        raise ValueError(f"unsupported absent_policy: {absent_policy}")

    suffix = ""
    if dataset_class == "optional_stress":
        suffix = f"_{array_profile}_{absent_policy}"
    case_id = (
        f"{dataset_class}_n{array_size}_q{query_count}_{scenario}{suffix}"
    )

    return SyntheticConfig(
        case_id=case_id,
        dataset_class=dataset_class,
        array_size=array_size,
        query_count=query_count,
        scenario=scenario,
        array_profile=array_profile,
        absent_policy=absent_policy,
        array_seed=_derive_array_seed(
            array_size,
            array_profile,
            dataset_class,
        ),
        query_seed=_derive_query_seed(
            array_size,
            query_count,
            scenario,
            array_profile,
            absent_policy,
            dataset_class,
        ),
    )


def mandatory_configurations() -> tuple[SyntheticConfig, ...]:
    """Return the full 3 x 2 x 3 mandatory benchmark matrix."""

    configurations = []
    for array_size in MANDATORY_ARRAY_SIZES:
        for query_count in MANDATORY_QUERY_COUNTS:
            for scenario in MANDATORY_SCENARIOS:
                configurations.append(
                    make_configuration(
                        array_size,
                        query_count,
                        scenario,
                        dataset_class="mandatory_benchmark",
                        array_profile=DEFAULT_ARRAY_PROFILE,
                        absent_policy=DEFAULT_ABSENT_POLICY,
                    )
                )
    return tuple(configurations)


def _generate_array(config: SyntheticConfig) -> list[int]:
    rng = random.Random(config.array_seed)
    upper_bound = config.id_range_multiplier * config.array_size

    if config.array_profile == "sampling_with_replacement":
        return [rng.randrange(upper_bound) for _ in range(config.array_size)]

    if config.array_profile == "all_unique":
        return rng.sample(range(upper_bound), config.array_size)

    if config.array_profile == "all_identical":
        value = rng.randrange(upper_bound)
        return [value] * config.array_size

    if config.array_profile == "high_duplicate":
        pool_size = max(1, config.array_size // 100)
        pool = rng.sample(range(upper_bound), pool_size)
        return [rng.choice(pool) for _ in range(config.array_size)]

    raise ValueError(f"unsupported array_profile: {config.array_profile}")


def _query_mix(config: SyntheticConfig) -> tuple[int, int, float]:
    if config.scenario == "all_present":
        return config.query_count, 0, 1.0

    if config.scenario == "all_absent":
        return 0, config.query_count, 0.0

    if config.query_count == 1:
        present_count = 1 if config.query_seed % 2 == 0 else 0
        return present_count, 1 - present_count, 0.5

    present_count = config.query_count // 2
    return present_count, config.query_count - present_count, 0.5


def _sample_present_queries(
    unique_values: list[int],
    count: int,
    rng: random.Random,
) -> tuple[list[int], str]:
    if count == 0:
        return [], "not_applied"
    if count <= len(unique_values):
        return rng.sample(unique_values, count), "without_replacement"
    return (
        [rng.choice(unique_values) for _ in range(count)],
        "with_replacement_due_to_cardinality",
    )


def _within_range_absent_queries(
    used_values: set[int],
    count: int,
    upper_bound: int,
    rng: random.Random,
) -> list[int]:
    selected: list[int] = []
    selected_set: set[int] = set()

    available_count = upper_bound - len(used_values)
    if count > available_count:
        raise ValueError("not enough within-range absent values are available")

    while len(selected) < count:
        candidate = rng.randrange(upper_bound)
        if candidate not in used_values and candidate not in selected_set:
            selected.append(candidate)
            selected_set.add(candidate)
    return selected


def _outside_range_absent_queries(
    count: int,
    upper_bound: int,
    query_seed: int,
) -> list[int]:
    selected = []
    start_with_low = query_seed % 2 == 0
    low_offset = 1
    high_offset = 0

    for index in range(count):
        choose_low = (index % 2 == 0) == start_with_low
        if choose_low:
            selected.append(-low_offset)
            low_offset += 1
        else:
            selected.append(upper_bound + high_offset)
            high_offset += 1
    return selected


def _generate_queries(
    array: list[int],
    config: SyntheticConfig,
) -> tuple[list[int], dict[str, Any]]:
    rng = random.Random(config.query_seed)
    used_values = set(array)
    unique_values = sorted(used_values)
    upper_bound = config.id_range_multiplier * config.array_size
    present_count, absent_count, target_hit_rate = _query_mix(config)

    present_queries, present_query_policy = _sample_present_queries(
        unique_values,
        present_count,
        rng,
    )

    if config.absent_policy == "within_range_gap":
        absent_queries = _within_range_absent_queries(
            used_values,
            absent_count,
            upper_bound,
            rng,
        )
    elif config.absent_policy == "outside_range_balanced":
        absent_queries = _outside_range_absent_queries(
            absent_count,
            upper_bound,
            config.query_seed,
        )
    else:
        raise ValueError(f"unsupported absent_policy: {config.absent_policy}")

    queries = present_queries + absent_queries
    rng.shuffle(queries)

    hit_count = sum(query in used_values for query in queries)
    actual_hit_rate = hit_count / len(queries)
    true_mixed_batch = 0 < hit_count < len(queries)

    query_metadata = {
        "target_hit_rate": target_hit_rate,
        "actual_hit_rate": actual_hit_rate,
        "hit_count": hit_count,
        "is_true_mixed_batch": true_mixed_batch,
        "mixed_singleton_policy": (
            "present_if_query_seed_even"
            if config.scenario == "mixed" and config.query_count == 1
            else None
        ),
        "present_query_policy": present_query_policy,
        "query_order_policy": "deterministic_shuffle",
        "absent_policy_applied": absent_count > 0,
    }
    return queries, query_metadata


def _fingerprint(values: list[int]) -> str:
    payload = json.dumps(values, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _environment_metadata() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "python_full_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "operating_system": platform.system(),
        "platform": platform.platform(),
        "machine_architecture": platform.machine(),
    }


def generate_case(config: SyntheticConfig) -> SyntheticCase:
    """Generate one deterministic case without running any search method."""

    array = _generate_array(config)
    queries, query_metadata = _generate_queries(array, config)

    unique_count = len(set(array))
    duplicate_count = len(array) - unique_count
    duplicate_rate = duplicate_count / len(array) if array else 0.0
    query_unique_count = len(set(queries))

    metadata: dict[str, Any] = {
        "case_id": config.case_id,
        "dataset_class": config.dataset_class,
        "generator_version": GENERATOR_VERSION,
        "seed_schema_version": SEED_SCHEMA_VERSION,
        "array_size": config.array_size,
        "query_count": config.query_count,
        "scenario": config.scenario,
        "array_profile": config.array_profile,
        "array_seed": config.array_seed,
        "query_seed": config.query_seed,
        "id_range_min_inclusive": 0,
        "id_range_max_exclusive": (
            config.id_range_multiplier * config.array_size
        ),
        "duplicate_policy": config.array_profile,
        "duplicates_allowed": config.array_profile != "all_unique",
        "duplicates_forced": config.array_profile == "all_identical",
        "unique_count": unique_count,
        "duplicate_count": duplicate_count,
        "duplicate_rate": duplicate_rate,
        "query_unique_count": query_unique_count,
        "query_duplicate_count": len(queries) - query_unique_count,
        "absent_policy": config.absent_policy,
        "array_fingerprint_sha256": _fingerprint(array),
        "query_fingerprint_sha256": _fingerprint(queries),
        **query_metadata,
        **_environment_metadata(),
    }
    return SyntheticCase(array=array, queries=queries, metadata=metadata)


def generate_mandatory_cases() -> tuple[SyntheticCase, ...]:
    """Generate all 18 mandatory cases; generation is never timed here."""

    return tuple(generate_case(config) for config in mandatory_configurations())
