"""Deterministic benchmark datasets, checksums, and stable gzip storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import random
from types import ModuleType
from typing import Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = PROJECT_ROOT / "tools" / "generate_orders.py"


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "assignment1_measurement_generator", GENERATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load supplied generator: {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = _load_generator()
STREAM_SCENARIOS = tuple(GENERATOR.SCENARIOS)


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """Complete identity of one pre-generated synthetic input."""

    experiment: str
    scenario: str
    event_count: int
    seed: int
    levels: int

    def __post_init__(self) -> None:
        if self.experiment not in {"stream", "queue_concentration", "liquidation"}:
            raise ValueError(f"unknown experiment: {self.experiment}")
        if type(self.event_count) is not int or self.event_count < 1:
            raise ValueError("event_count must be a positive integer")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")
        if type(self.levels) is not int or not 1 <= self.levels < 6_000_000:
            raise ValueError("levels must be between 1 and 5,999,999")
        if self.experiment in {"stream", "queue_concentration"}:
            if self.scenario not in STREAM_SCENARIOS:
                raise ValueError(f"unknown supplied scenario: {self.scenario}")
        elif self.scenario != "bid_book":
            raise ValueError("liquidation datasets must use scenario='bid_book'")

    @property
    def dataset_id(self) -> str:
        return (
            f"{self.experiment}__{self.scenario}__m{self.event_count}"
            f"__seed{self.seed}__levels{self.levels}"
        )


def _event_line(event: Mapping[str, object]) -> bytes:
    return (
        json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def event_checksum(events: Iterable[Mapping[str, object]]) -> str:
    digest = hashlib.sha256()
    for event in events:
        digest.update(_event_line(event))
    return digest.hexdigest()


def _liquidation_events(spec: DatasetSpec) -> tuple[dict[str, object], ...]:
    rng = random.Random(spec.seed)
    rows: list[dict[str, object]] = []
    for seq in range(1, spec.event_count + 1):
        event_id = f"liq{seq:09d}"
        rows.append(
            {
                "seq": seq,
                "event_id": event_id,
                "type": "LIMIT",
                "order_id": event_id,
                "side": "BUY",
                "price_ticks": 6_000_000 - rng.randrange(spec.levels),
                "qty_units": rng.randint(1, 100) * 1_000_000,
            }
        )
    return tuple(rows)


def generate_events(spec: DatasetSpec) -> tuple[dict[str, object], ...]:
    """Generate one immutable-by-convention event tuple outside measurement."""

    if spec.experiment == "liquidation":
        return _liquidation_events(spec)
    return tuple(
        dict(event)
        for event in GENERATOR.events(
            spec.scenario,
            spec.event_count,
            spec.seed,
            spec.levels,
        )
    )


def liquidation_request(total_bid_qty: int, percent: int) -> int:
    """Return the integer sale request, rounding positive percentages up."""

    if type(total_bid_qty) is not int or total_bid_qty < 1:
        raise ValueError("total_bid_qty must be a positive integer")
    if type(percent) is not int or percent < 1:
        raise ValueError("percent must be a positive integer")
    return max(1, (total_bid_qty * percent + 99) // 100)


def metadata_path(data_path: Path) -> Path:
    return data_path.with_suffix(data_path.suffix + ".metadata.json")


def write_dataset(
    path: Path,
    spec: DatasetSpec,
    events: tuple[dict[str, object], ...] | None = None,
) -> dict[str, object]:
    """Write stable gzip bytes and complete generator/checksum metadata."""

    rows = generate_events(spec) if events is None else events
    if len(rows) != spec.event_count:
        raise ValueError("event tuple length does not match DatasetSpec")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
            for event in rows:
                stream.write(_event_line(event))

    compressed = path.read_bytes()
    metadata: dict[str, object] = {
        **asdict(spec),
        "dataset_id": spec.dataset_id,
        "synthetic": True,
        "calibrated_to_exchange_data": False,
        "generator": (
            "custom_bid_book_random.Random"
            if spec.experiment == "liquidation"
            else "course_generate_orders.events"
        ),
        "generator_python": platform.python_version(),
        "price_tick_usd": "0.01",
        "quantity_unit_btc": "0.00000001",
        "compressed_bytes": len(compressed),
        "compressed_sha256": hashlib.sha256(compressed).hexdigest(),
        "event_sha256": event_checksum(rows),
    }
    metadata_path(path).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def read_events(path: Path) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: event must be an object")
            rows.append(value)
    return tuple(rows)


def load_dataset(path: Path) -> tuple[tuple[dict[str, object], ...], dict[str, object]]:
    """Load and verify bytes, event count, sequence, and canonical event hash."""

    metadata = json.loads(metadata_path(path).read_text(encoding="utf-8"))
    compressed = path.read_bytes()
    if len(compressed) != metadata["compressed_bytes"]:
        raise ValueError(f"compressed byte count mismatch: {path}")
    if hashlib.sha256(compressed).hexdigest() != metadata["compressed_sha256"]:
        raise ValueError(f"compressed checksum mismatch: {path}")

    rows = read_events(path)
    if len(rows) != metadata["event_count"]:
        raise ValueError(f"event count mismatch: {path}")
    if [event.get("seq") for event in rows] != list(range(1, len(rows) + 1)):
        raise ValueError(f"sequence mismatch: {path}")
    if event_checksum(rows) != metadata["event_sha256"]:
        raise ValueError(f"event checksum mismatch: {path}")
    return rows, metadata


def standard_specs(
    sizes: Iterable[int],
    seeds: Iterable[int],
    scenarios: Iterable[str] = STREAM_SCENARIOS,
    levels: int = 1_000,
    include_special: bool = True,
) -> tuple[DatasetSpec, ...]:
    """Create the declared stream, concentration, and liquidation grid."""

    size_values = tuple(sizes)
    seed_values = tuple(seeds)
    specs = [
        DatasetSpec("stream", scenario, size, seed, levels)
        for scenario in scenarios
        for size in size_values
        for seed in seed_values
    ]
    if include_special:
        specs.extend(
            DatasetSpec("queue_concentration", "buildup", size, seed, queue_levels)
            for size in size_values
            for seed in seed_values
            for queue_levels in (4, 1_000)
        )
        specs.extend(
            DatasetSpec("liquidation", "bid_book", size, seed, levels)
            for size in size_values
            for seed in seed_values
        )
    return tuple(specs)
