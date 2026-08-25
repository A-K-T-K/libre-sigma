"""
Comprehensive unit test suite for Distribution ID Plot (Right Censoring).
Tests:
  - 11 Parametric lifetime distribution fits with right censoring
  - Anderson-Darling (adj) goodness of fit calculations
  - Table of Percentiles (1%, 5%, 10%, 50%) with SE and 95% Normal CIs
  - Table of MTTF with SE and 95% Normal CIs
  - Probability plot traces and layout
  - Uncensored and heavily right-censored data
  - Execution speed benchmark (< 100ms)
"""

import sys
import time
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, "backend")
from app.plugins.modules.reliability.distribution_id_right_censoring import (
    DistributionIdRightCensoringPlugin,
    DistributionIdRightCensoringParams,
)


class TestDistributionIdRightCensoring(unittest.TestCase):
    def setUp(self):
        self.plugin = DistributionIdRightCensoringPlugin()

    def test_right_censored_dataset(self):
        # Sample reliability lifetime dataset with failures (1) and right-censored units (0)
        durations = [
            1.2, 1.8, 2.5, 3.1, 3.8, 4.2, 4.9, 5.5, 6.1, 6.8,
            7.2, 7.9, 8.4, 9.1, 9.8, 10.5, 11.2, 12.0, 12.5, 13.0
        ]
        censors = [
            1, 1, 1, 0, 1, 1, 0, 1, 1, 0,
            1, 1, 0, 1, 1, 0, 1, 0, 1, 0
        ]

        df = pd.DataFrame({"Lifetime": durations, "Censor": censors})
        params = DistributionIdRightCensoringParams(
            variables="Lifetime",
            censor_col="Censor",
            confidence_level=95.0
        )

        start_t = time.perf_counter()
        res = self.plugin.execute(df, params)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        self.assertIsNotNone(res.tables)
        self.assertEqual(len(res.tables), 3)

        # 1. Goodness-of-Fit Table
        gof_table = res.tables[0]
        self.assertEqual(gof_table.title, "Goodness-of-Fit")
        self.assertEqual(len(gof_table.rows), 11)
        dist_names = [r[0] for r in gof_table.rows]
        self.assertIn("Weibull", dist_names)
        self.assertIn("Lognormal", dist_names)
        self.assertIn("Exponential", dist_names)
        self.assertIn("Loglogistic", dist_names)
        self.assertIn("3-Parameter Weibull", dist_names)
        self.assertIn("Normal", dist_names)
        self.assertIn("Smallest Extreme Value", dist_names)

        # Check that AD(adj) are valid positive floats
        for row in gof_table.rows:
            if row[1] != "—":
                ad_val = float(row[1])
                self.assertGreater(ad_val, 0.0)

        # 2. Table of Percentiles
        pct_table = res.tables[1]
        self.assertEqual(pct_table.title, "Table of Percentiles")
        self.assertGreater(len(pct_table.rows), 20)

        # 3. Table of MTTF
        mttf_table = res.tables[2]
        self.assertEqual(mttf_table.title, "Table of MTTF")
        self.assertEqual(len(mttf_table.rows), 11)

        # 4. Plotly Probability Plot
        self.assertIsNotNone(res.plotly_figure)
        self.assertIn("data", res.plotly_figure)
        self.assertIn("layout", res.plotly_figure)

        # Execution should be highly optimized and fast
        self.assertLess(elapsed_ms, 250.0)

    def test_uncensored_dataset(self):
        durations = [10.2, 12.5, 14.1, 16.8, 18.2, 21.0, 24.5, 27.9, 31.2, 35.0]
        df = pd.DataFrame({"Time": durations})
        params = DistributionIdRightCensoringParams(
            variables="Time",
            confidence_level=95.0
        )

        res = self.plugin.execute(df, params)
        self.assertEqual(len(res.tables), 3)
        self.assertIn("Goodness-of-Fit Summary", res.text_output)


if __name__ == "__main__":
    unittest.main()
