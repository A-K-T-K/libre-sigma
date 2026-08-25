import unittest
import pandas as pd
import numpy as np

from app.plugins.modules.reliability.nonparametric_distribution import (
    NonparametricDistributionPlugin,
    NonparametricDistributionParams
)


class TestNonparametricDistribution(unittest.TestCase):
    def setUp(self):
        self.plugin = NonparametricDistributionPlugin()
        self.data = [4, 5, 5, 6, 6, 7, 7, 8, 8, 8, 9, 9]
        self.df = pd.DataFrame({"C1": self.data})

    def test_uncensored_characteristics(self):
        params = NonparametricDistributionParams(variables="C1")
        result = self.plugin.execute(self.df, params)

        # Check Censoring Table
        censoring_table = next(t for t in result.tables if "Censoring" in t.title)
        self.assertEqual(censoring_table.rows[0][1], 12)  # 12 Uncensored
        self.assertEqual(censoring_table.rows[1][1], 0)   # 0 Censored

        # Check Characteristics Table
        char_table = next(t for t in result.tables if "Characteristics" in t.title)
        mttf = char_table.rows[0][0]
        se = char_table.rows[0][1]
        q1 = char_table.rows[0][4]
        median = char_table.rows[0][5]
        q3 = char_table.rows[0][6]
        iqr = char_table.rows[0][7]

        # MTTF should be sum of area under KM curve
        self.assertAlmostEqual(mttf, 6.83333, places=3)
        
        # Standard Error
        self.assertAlmostEqual(se, 0.474075, places=3)
        
        self.assertEqual(q1, 5)
        self.assertEqual(median, 7)
        self.assertEqual(q3, 8)
        self.assertEqual(iqr, 3)

        # Check Kaplan-Meier Table (first row for time=4)
        km_table = next(t for t in result.tables if "Kaplan-Meier" in t.title)
        row_t4 = km_table.rows[0]
        self.assertEqual(row_t4[0], 4.0) # Time
        self.assertEqual(row_t4[1], 12)  # At risk
        self.assertEqual(row_t4[2], 1)   # Failed
        self.assertAlmostEqual(row_t4[3], 0.916667, places=4) # Surv Prob
        self.assertAlmostEqual(row_t4[4], 0.079786, places=4) # SE

if __name__ == "__main__":
    unittest.main()
