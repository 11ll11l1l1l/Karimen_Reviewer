import json
import tempfile
import unittest
from pathlib import Path

from database import Database
from inbound_integrations import process_inbound_endpoint, process_inbound_file


class InboundIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.source=self.root/"source";self.archive=self.root/"archive";self.quarantine=self.root/"quarantine"
        self.source.mkdir()
        self.db=Database("sqlite:///:memory:")
        self.db.save_equipment({"equipment_id":"ETCH-IN","name":"Inbound Etcher"},user="seed")
        self.db.save_meter({
            "equipment_id":"ETCH-IN","meter_code":"RF_HOURS","name":"RF Hours","unit":"h",
            "current_value":0.0,"active":True,"meter_mode":"COUNTER",
        })

    def tearDown(self):
        self.tmp.cleanup()

    def test_json_alarm_feed_applies_archives_and_is_idempotent(self):
        self.db.save_inbound_endpoint({
            "endpoint_id":"FDC-ALARM","name":"FDC alarms","adapter_type":"FILE_JSON","entity_type":"ALARM",
            "source_path":str(self.source),"file_pattern":"*.json",
            "mapping_json":{
                "equipment_id":"tool","alarm_code":"alarm.code","severity":"alarm.severity",
                "message":"alarm.text","occurred_at":"time",
            },
            "defaults_json":{"state":"ACTIVE","source":"FDC"},
            "archive_path":str(self.archive),"quarantine_path":str(self.quarantine),"enabled":True,
        })
        payload={"records":[
            {"tool":"ETCH-IN","alarm":{"code":"VAC-01","severity":"Critical","text":"Vacuum trip"},"time":"2026-09-24T05:00:00Z"},
            {"tool":"ETCH-IN","alarm":{"code":"TEMP-02","severity":"Warning","text":"Temperature high"},"time":"2026-09-24T05:01:00+00:00"},
        ]}
        source=self.source/"alarms.json";source.write_text(json.dumps(payload),encoding="utf-8")
        result=process_inbound_endpoint(self.db,"FDC-ALARM")
        self.assertEqual(result["processed"],1)
        self.assertEqual(result["applied"],2)
        self.assertEqual(len(self.db.list_alarms("ETCH-IN",False)),2)
        self.assertFalse(source.exists())
        self.assertEqual(len(list(self.archive.glob("alarms*.json"))),1)
        receipt=self.db.list_inbound_receipts("FDC-ALARM")[0]
        self.assertEqual(receipt.status,"Processed")
        records=self.db.list_inbound_records("FDC-ALARM",receipt.id)
        self.assertEqual({x.status for x in records},{"Applied"})

        # Re-arrival of the exact same payload must not create duplicate target records.
        duplicate=self.source/"alarms_again.json";duplicate.write_text(json.dumps(payload),encoding="utf-8")
        duplicate_result=process_inbound_endpoint(self.db,"FDC-ALARM")
        self.assertEqual(duplicate_result["duplicates"],1)
        self.assertEqual(len(self.db.list_alarms("ETCH-IN",False)),2)
        self.assertFalse(duplicate.exists())

    def test_csv_meter_feed_records_readings(self):
        self.db.save_inbound_endpoint({
            "endpoint_id":"FDC-METER","name":"FDC meters","adapter_type":"FILE_CSV","entity_type":"METER",
            "source_path":str(self.source),"file_pattern":"*.csv",
            "mapping_json":{"equipment_id":"tool","meter_code":"counter","value":"reading","note":"note"},
            "defaults_json":{},"archive_path":str(self.archive),"quarantine_path":str(self.quarantine),"enabled":True,
        })
        source=self.source/"meters.csv"
        source.write_text("tool,counter,reading,note\nETCH-IN,RF_HOURS,12.5,Shift read\nETCH-IN,RF_HOURS,18.0,Later read\n",encoding="utf-8")
        result=process_inbound_endpoint(self.db,"FDC-METER")
        self.assertEqual(result["applied"],2)
        readings=self.db.list_meter_readings("ETCH-IN","RF_HOURS")
        self.assertEqual([x.value for x in readings],[18.0,12.5])
        self.assertTrue(all(x.recorded_by=="integration:FDC-METER" for x in readings))
        self.assertEqual(self.db.list_meters("ETCH-IN")[0].current_value,18.0)

    def test_invalid_file_is_quarantined_before_target_writes(self):
        self.db.save_inbound_endpoint({
            "endpoint_id":"BAD-ALARM","name":"Bad alarms","adapter_type":"FILE_JSON","entity_type":"ALARM",
            "source_path":str(self.source),"file_pattern":"*.json",
            "mapping_json":{"equipment_id":"tool","alarm_code":"code"},"defaults_json":{},
            "archive_path":str(self.archive),"quarantine_path":str(self.quarantine),"enabled":True,
        })
        source=self.source/"bad.json"
        source.write_text(json.dumps([{"tool":"ETCH-IN","code":"A1"},{"tool":"NO-TOOL","code":"A2"}]),encoding="utf-8")
        result=process_inbound_endpoint(self.db,"BAD-ALARM")
        self.assertEqual(result["quarantined"],1)
        self.assertEqual(result["applied"],0)
        self.assertEqual(len(self.db.list_alarms("ETCH-IN",False)),0)
        receipt=self.db.list_inbound_receipts("BAD-ALARM")[0]
        self.assertEqual(receipt.status,"Quarantined")
        self.assertEqual(receipt.records_rejected,1)
        self.assertTrue(any(self.quarantine.iterdir()))

    def test_replay_skips_already_applied_records(self):
        self.db.save_inbound_endpoint({
            "endpoint_id":"METER-REPLAY","name":"Meter replay","adapter_type":"FILE_CSV","entity_type":"METER",
            "source_path":str(self.source),"file_pattern":"*.csv",
            "mapping_json":{"equipment_id":"tool","meter_code":"counter","value":"reading"},"defaults_json":{},
            "archive_path":str(self.archive),"quarantine_path":str(self.quarantine),"enabled":True,
        })
        source=self.source/"one.csv";source.write_text("tool,counter,reading\nETCH-IN,RF_HOURS,7\n",encoding="utf-8")
        first=process_inbound_endpoint(self.db,"METER-REPLAY")
        self.assertEqual(first["applied"],1)
        receipt=self.db.list_inbound_receipts("METER-REPLAY")[0]
        final_path=json.loads(receipt.detail_json)["final_path"]
        replay=process_inbound_file(self.db,"METER-REPLAY",final_path,replay=True)
        self.assertEqual(replay["applied"],0)
        self.assertEqual(replay["skipped"],1)
        self.assertEqual(len(self.db.list_meter_readings("ETCH-IN","RF_HOURS")),1)


if __name__=="__main__":
    unittest.main()
