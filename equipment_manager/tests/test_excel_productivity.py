import unittest

import pandas as pd

from services import auto_mapping, dataframe_to_equipment, dataframe_to_inventory


class ExcelProductivityTests(unittest.TestCase):
    def test_equipment_dataframe_normalization(self):
        df=pd.DataFrame([
            {"Tool ID":"ETCH-A01","Equipment Name":"Etcher A01","Maker":"Vendor","Model":"X1","Area":"ETCH","Bay":"BAY-A","Owner":"ee"},
            {"Tool ID":"","Equipment Name":"Missing ID"},
        ])
        mapping=auto_mapping(list(df.columns))
        rows,errors=dataframe_to_equipment(df,mapping)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["equipment_id"],"ETCH-A01")
        self.assertEqual(rows[0]["manufacturer"],"Vendor")
        self.assertEqual(rows[0]["line_cell"],"BAY-A")
        self.assertTrue(errors)

    def test_inventory_dataframe_normalization(self):
        df=pd.DataFrame([
            {"Part No":"FILTER-1","Description":"Process filter","Qty":12,"Min Qty":4,"Location":"STOCK-A","Unit":"ea"},
            {"Part No":"BAD","Qty":-2,"Location":"STOCK-A"},
        ])
        mapping=auto_mapping(list(df.columns))
        rows,errors=dataframe_to_inventory(df,mapping)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["part_number"],"FILTER-1")
        self.assertEqual(rows[0]["location_code"],"STOCK-A")
        self.assertEqual(rows[0]["quantity"],12)
        self.assertTrue(errors)


if __name__=="__main__":
    unittest.main()
