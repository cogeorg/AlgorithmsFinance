"""State-independent validation contract tests."""

import unittest

from orderbook.validation import validate_event
from support import limit


class TestStatelessValidation(unittest.TestCase):
    def test_valid_limit_has_no_stateless_rejection(self) -> None:
        self.assertIsNone(validate_event(limit(1, "e1", "b1", "BUY", 100, 1)))

    def test_non_dictionary_event_is_rejected(self) -> None:
        for event in (None, [], "event", 1, True):
            with self.subTest(event=event):
                result = validate_event(event)
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(result["reason"], "invalid_event")
                self.assertNotIn("event_id", result)

    def test_missing_required_fields_are_rejected(self) -> None:
        event = {"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1", "side": "BUY"}
        self.assertEqual(validate_event(event), {"event_id": "e1", "status": "rejected", "reason": "missing_field"})

    def test_exact_integer_validation_rejects_bool_float_string_and_none(self) -> None:
        for field in ("seq", "price_ticks", "qty_units"):
            for value in (True, False, 1.5, "1", None):
                with self.subTest(field=field, value=value):
                    event = limit(1, "e1", "b1", "BUY", 100, 1)
                    event[field] = value
                    result = validate_event(event)
                    self.assertEqual(result["status"], "rejected")
                    self.assertEqual(result["reason"], "invalid_field_type")

    def test_zero_and_negative_numeric_values_are_rejected(self) -> None:
        reasons = {"seq": "invalid_sequence", "price_ticks": "nonpositive_price", "qty_units": "nonpositive_quantity"}
        for field, reason in reasons.items():
            for value in (0, -1):
                with self.subTest(field=field, value=value):
                    event = limit(1, "e1", "b1", "BUY", 100, 1)
                    event[field] = value
                    self.assertEqual(validate_event(event), {"event_id": "e1", "status": "rejected", "reason": reason})

    def test_unknown_type_and_side_are_rejected(self) -> None:
        bad_type = limit(1, "e1", "b1", "BUY", 100, 1)
        bad_type["type"] = "UNKNOWN"
        self.assertEqual(validate_event(bad_type), {"event_id": "e1", "status": "rejected", "reason": "invalid_event_type"})
        bad_side = limit(1, "e1", "b1", "BUY", 100, 1)
        bad_side["side"] = "BID"
        self.assertEqual(validate_event(bad_side), {"event_id": "e1", "status": "rejected", "reason": "invalid_side"})

    def test_identifiers_must_be_nonempty_exact_strings(self) -> None:
        for field in ("event_id", "order_id"):
            for value in ("", 1, True, None):
                with self.subTest(field=field, value=value):
                    event = limit(1, "e1", "b1", "BUY", 100, 1)
                    event[field] = value
                    result = validate_event(event)
                    self.assertEqual(result["status"], "rejected")
                    self.assertEqual(result["reason"], "invalid_identifier")

    def test_extra_fields_are_ignored(self) -> None:
        event = limit(1, "e1", "b1", "BUY", 100, 1)
        event["unrelated_metadata"] = {"source": "test"}
        self.assertIsNone(validate_event(event))

    def test_multiple_invalid_fields_do_not_require_reason_precedence(self) -> None:
        event = {"seq": True, "event_id": "e1", "type": "LIMIT", "order_id": "", "side": "BAD", "price_ticks": 0}
        result = validate_event(event)
        self.assertEqual(result["status"], "rejected")
        self.assertIsInstance(result["reason"], str)
        self.assertTrue(result["reason"])


if __name__ == "__main__":
    unittest.main()

