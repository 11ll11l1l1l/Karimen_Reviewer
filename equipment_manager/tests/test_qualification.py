import unittest

from database import Database


RELEASE_CHECKS = {
    "maintenance_complete": True,
    "measurements_pass": True,
    "calibration_valid": True,
    "safety_check": True,
    "verification_run": True,
    "critical_tickets_cleared": True,
}


class QualificationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.db=Database("sqlite:///:memory:")
        self.db.save_equipment({
            "equipment_id":"ETCH-01",
            "name":"Etcher",
            "equipment_type":"Plasma Etcher",
            "owner":"EE-A",
        },user="seed")
        self.protocol=self.db.save_qualification_protocol(
            "QUAL-ETCH-BASE",
            "Etcher return-to-service qualification",
            [
                {"check_id":"Q01","label":"Vacuum leak rate","acceptance":"Pass"},
                {"check_id":"Q02","label":"RF match verification","acceptance":"Pass"},
                {"check_id":"Q03","label":"Monitor wafer result","acceptance":"Pass"},
            ],
            "author",
            equipment_type="Plasma Etcher",
        )

    def _complete_run(self):
        run=self.db.start_qualification_run("ETCH-01","QUAL-ETCH-BASE","executor")
        for check_id in ["Q01","Q02","Q03"]:
            run=self.db.save_qualification_result(
                run.id,check_id,"PASS","Passed controlled check","executor",
                expected_version=run.version,
            )
        run=self.db.submit_qualification_run(
            run.id,"executor","All protocol checks passed",expected_version=run.version
        )
        return run

    def test_protocol_revision_is_frozen_in_run(self):
        run=self.db.start_qualification_run("ETCH-01","QUAL-ETCH-BASE","executor")
        checks,_=self.db.qualification_run_checks(run.id)
        self.assertEqual(run.protocol_revision,1)
        self.assertEqual(len(checks),3)

        revised=self.db.save_qualification_protocol(
            "QUAL-ETCH-BASE",
            "Etcher return-to-service qualification",
            [
                {"check_id":"Q01","label":"Vacuum leak rate"},
                {"check_id":"Q02","label":"RF match verification"},
                {"check_id":"Q03","label":"Monitor wafer result"},
                {"check_id":"Q04","label":"Particle check"},
            ],
            "author",
            equipment_type="Plasma Etcher",
            create_revision=True,
        )
        self.assertEqual(revised.revision,2)
        frozen,_=self.db.qualification_run_checks(run.id)
        self.assertEqual(len(frozen),3)

    def test_failed_check_blocks_submission(self):
        run=self.db.start_qualification_run("ETCH-01","QUAL-ETCH-BASE","executor")
        run=self.db.save_qualification_result(run.id,"Q01","FAIL","Leak high","executor",expected_version=run.version)
        run=self.db.save_qualification_result(run.id,"Q02","PASS","OK","executor",expected_version=run.version)
        run=self.db.save_qualification_result(run.id,"Q03","PASS","OK","executor",expected_version=run.version)
        with self.assertRaises(ValueError):
            self.db.submit_qualification_run(run.id,"executor",expected_version=run.version)

    def test_independent_verification_and_approval(self):
        run=self._complete_run()
        with self.assertRaises(ValueError):
            self.db.verify_qualification_run(run.id,"executor",expected_version=run.version)

        run=self.db.verify_qualification_run(
            run.id,"verifier","Reviewed raw data",expected_version=run.version
        )
        self.assertEqual(run.status,"Verified")

        with self.assertRaises(ValueError):
            self.db.approve_qualification_run(run.id,"verifier",expected_version=run.version)

        run=self.db.approve_qualification_run(
            run.id,"manager",valid_days=30,note="Approved for production",
            expected_version=run.version,
        )
        self.assertEqual(run.status,"Approved")
        self.assertEqual(self.db.latest_valid_qualification("ETCH-01").run_no,run.run_no)

    def test_release_from_qualification_requires_approved_run(self):
        eq=self.db.get_equipment("ETCH-01")
        self.db.transition_equipment_state(
            "ETCH-01","Qualification",
            reason_code="QUALIFICATION",reason_text="Hardware change",
            owner="EE-A",user="engineer",expected_version=eq.version,
        )
        pre=self.db.release_precheck("ETCH-01")
        self.assertTrue(pre["qualification_required"])
        self.assertFalse(pre["qualification_valid"])

        request=self.db.create_release_request(
            "ETCH-01","",RELEASE_CHECKS,"Release after qualification","requester"
        )
        verified=self.db.verify_release(
            request.id,RELEASE_CHECKS,"release_verifier",request.version
        )
        with self.assertRaises(ValueError):
            self.db.approve_release(
                verified.id,"release_manager",verified.version
            )

        run=self._complete_run()
        run=self.db.verify_qualification_run(run.id,"qual_verifier",expected_version=run.version)
        run=self.db.approve_qualification_run(run.id,"qual_manager",valid_days=30,expected_version=run.version)
        pre=self.db.release_precheck("ETCH-01")
        self.assertTrue(pre["qualification_valid"])
        self.assertEqual(pre["qualification_run_no"],run.run_no)

        # Release requester/verifier/approver remain independent.
        fresh=self.db.create_release_request(
            "ETCH-01","",RELEASE_CHECKS,"Qualified release","requester_2"
        )
        fresh=self.db.verify_release(fresh.id,RELEASE_CHECKS,"release_verifier_2",fresh.version)
        approved=self.db.approve_release(fresh.id,"release_manager_2",fresh.version)
        self.assertEqual(approved.status,"Approved / Released")


if __name__=="__main__":
    unittest.main()
