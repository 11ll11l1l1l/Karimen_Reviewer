from datetime import datetime, timedelta
import unittest

from alarm_correlation import correlate_alarm_bursts


class AlarmCorrelationTests(unittest.TestCase):
    def test_groups_adjacent_events_and_preserves_ids(self):
        start = datetime(2026, 9, 23, 8, 0, 0)
        bursts = correlate_alarm_bursts([
            {"id": "a2", "equipment_id": "ETCH-1", "alarm_code": "VAC", "severity": "HIGH", "occurred_at": start + timedelta(seconds=20)},
            {"id": "a1", "equipment_id": "ETCH-1", "alarm_code": "VAC", "severity": "LOW", "occurred_at": start},
            {"id": "a3", "equipment_id": "ETCH-1", "alarm_code": "TEMP", "severity": "CRITICAL", "occurred_at": start + timedelta(seconds=30)},
            {"id": "a4", "equipment_id": "ETCH-1", "alarm_code": "VAC", "severity": "LOW", "occurred_at": start + timedelta(seconds=400)},
        ])

        self.assertEqual(len(bursts), 3)
        self.assertEqual(bursts[0].alarm_ids, ("a1", "a2"))
        self.assertEqual(bursts[0].severity, "HIGH")
        self.assertEqual(bursts[0].count, 2)
        self.assertEqual(bursts[2].alarm_ids, ("a4",))

    def test_invalid_window_and_fields_fail_closed(self):
        with self.assertRaises(ValueError):
            correlate_alarm_bursts([], window_seconds=0)
        with self.assertRaises(ValueError):
            correlate_alarm_bursts([{"equipment_id": "E"}])


if __name__ == "__main__":
    unittest.main()
