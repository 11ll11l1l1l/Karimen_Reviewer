import unittest

from domain import allowed_targets, validate_transition, TransitionRuleViolation


class EquipmentStateMachineTests(unittest.TestCase):
    def test_production_to_down_requires_ticket_and_owner(self):
        with self.assertRaises(TransitionRuleViolation):
            validate_transition("Production", "Down", reason_code="FAILURE", reason_text="Vacuum trip", owner="EE")
        result = validate_transition(
            "Production", "Down",
            reason_code="FAILURE",
            reason_text="Vacuum trip during lot processing",
            related_ticket="INC-1001",
            owner="EE",
        )
        self.assertTrue(result.downtime)

    def test_down_cannot_jump_directly_to_production(self):
        with self.assertRaises(TransitionRuleViolation):
            validate_transition(
                "Down", "Production",
                reason_code="RELEASED",
                related_ticket="INC-1001",
                owner="EE",
            )

    def test_scheduled_pm_requires_pm_task(self):
        with self.assertRaises(TransitionRuleViolation):
            validate_transition(
                "Production", "PM",
                reason_code="PM_SCHEDULED",
                owner="Tech A",
            )

    def test_production_requires_released_disposition(self):
        with self.assertRaises(TransitionRuleViolation):
            validate_transition(
                "Qualification", "Production",
                reason_code="RELEASED",
                disposition="Quality Hold",
            )

    def test_waiting_parts_has_specific_reason(self):
        with self.assertRaises(TransitionRuleViolation):
            validate_transition(
                "Engineering", "Waiting Parts",
                reason_code="ENGINEERING_WORK",
                related_ticket="INC-1002",
                owner="EE",
            )

    def test_allowed_targets_are_governed(self):
        self.assertIn("Down", allowed_targets("Production"))
        self.assertNotIn("Production", allowed_targets("Down"))


if __name__ == "__main__":
    unittest.main()
