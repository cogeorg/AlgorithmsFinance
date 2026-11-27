"""The OWN datasets in 06_data/own/ are exactly what datagen/own_cases.py writes, and every
dataset has its contract check (check_own_<case>). These tests check data, not the engine,
so they already pass in the red run."""
import json

import contract
from datagen import own_cases


def test_every_case_has_a_contract_check():
    assert contract.OWN_CASES == own_cases.CASE_NAMES
    for name in own_cases.CASE_NAMES:
        assert callable(getattr(contract, f"check_own_{name}", None)), name


def test_files_on_disk_match_the_generator():
    texts = own_cases.all_texts()
    on_disk = {p.name for p in contract.OWN.iterdir() if p.is_file()}
    assert on_disk == set(texts), f"unexpected or missing files: {on_disk ^ set(texts)}"
    for name, text in texts.items():
        got = (contract.OWN / name).read_text(encoding="utf-8").splitlines()
        assert got == text.splitlines(), f"{name} differs from own_cases.py: run `python run.py datagen.own_cases`"


def test_expected_files_are_labelled_own_and_consistent():
    for name in own_cases.CASE_NAMES:
        exp = json.loads((contract.OWN / f"{name}.expected.json").read_text(encoding="utf-8"))
        events = contract.read_jsonl(contract.OWN / f"{name}.jsonl")
        assert exp["own"] is True and exp["synthetic"] is True and exp["case"] == name
        assert len(exp["results"]) == len(events), name
        assert exp["final_book"] == contract.canonical(exp["final_book"]), f"{name}: expected book not canonical"


def test_invalid_table_reasons_use_the_spec_codes():
    allowed_prefixes = ("missing_field:", "bad_id:")
    allowed = {"not_an_object", "bad_seq", "nonincreasing_seq", "unknown_type", "unknown_side",
               "bad_price", "bad_qty", "duplicate_live_order_id"}
    for row in own_cases.INVALID_EVENTS:
        assert row["reason"] in allowed or row["reason"].startswith(allowed_prefixes), row
