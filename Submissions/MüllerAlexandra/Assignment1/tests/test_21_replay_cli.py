"""The documented replay command exposes event results and canonical state."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from limit_order_book.replay_cli import build_replay_document, main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUPPLIED = PROJECT_ROOT / "data" / "supplied"


@pytest.mark.parametrize("version", ["baseline", "revised"])
def test_worked_example_replay_matches_independent_expected_result(
    version: str,
) -> None:
    expected = json.loads(
        (SUPPLIED / "worked_expected.json").read_text(encoding="utf-8")
    )

    document = build_replay_document(
        version=version,
        input_path=SUPPLIED / "worked_example.jsonl",
    )

    assert document["schema_version"] == 1
    assert document["version"] == version
    assert document["input"]["event_count"] == 6
    assert document["retained_event_results"] is True
    assert len(document["results"]) == 6
    assert document["results"][-1] == expected["market_sell_result"]
    assert document["final_book"] == expected["remaining_orders"]
    assert document["summary"] == {
        "event_count": 6,
        "rejected_event_count": 0,
        "final_active_orders": 2,
    }


def test_replay_accepts_gzip_json_lines(tmp_path: Path) -> None:
    compressed = tmp_path / "worked_example.jsonl.gz"
    with (
        (SUPPLIED / "worked_example.jsonl").open("rt", encoding="utf-8") as source,
        gzip.open(compressed, "wt", encoding="utf-8", newline="\n") as target,
    ):
        target.write(source.read())

    document = build_replay_document(version="baseline", input_path=compressed)

    assert document["input"]["gzip_compressed"] is True
    assert document["summary"]["event_count"] == 6
    assert document["results"][-1]["status"] == "filled"


def test_cli_writes_exclusive_json_output(tmp_path: Path) -> None:
    output = tmp_path / "replay.json"
    arguments = [
        "--version",
        "revised",
        "--input",
        str(SUPPLIED / "worked_example.jsonl"),
        "--out",
        str(output),
    ]

    assert main(arguments) == 0
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["version"] == "revised"
    assert document["summary"]["event_count"] == 6
    with pytest.raises(FileExistsError):
        main(arguments)


def test_cli_prints_json_when_output_is_omitted(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [
            "--version",
            "baseline",
            "--input",
            str(SUPPLIED / "worked_example.jsonl"),
        ]
    )

    assert exit_code == 0
    document = json.loads(capsys.readouterr().out)
    assert document["version"] == "baseline"
    assert document["final_book"][0]["order_id"] == "b4"
