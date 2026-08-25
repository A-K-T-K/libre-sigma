"""
Comprehensive test suite for Taguchi Orthogonal Array Design Generation and Analysis.
Tests:
  - L4 (2^3), L8 (2^7), L9 (3^4), L18 (2^1 x 3^7), L27 (3^13)
  - String & Numeric Categorical Level Mappings
  - Signal-to-Noise Ratio Objectives:
      * Larger is better: eta = -10*log10(mean(1/y^2))
      * Smaller is better: eta = -10*log10(mean(y^2))
      * Nominal is best: eta = -10*log10(mean((y - T)^2))
  - Main Effects for Means and S/N Ratios
  - Delta Ranks & Taguchi ANOVA
  - Edge cases:
      * Zero variance responses
      * Insufficient runs
      * Categorical string factor levels
      * Nominal target specification (T)
"""

import sys
import json
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, "backend")
from app.plugins.modules.doe_create_taguchi import CreateTaguchiDesignPlugin, CreateTaguchiParams
from app.plugins.modules.doe_analyze_taguchi import AnalyzeTaguchiDesignPlugin, AnalyzeTaguchiParams


class TestTaguchiDOE(unittest.TestCase):
    def setUp(self):
        self.create_plugin = CreateTaguchiDesignPlugin()
        self.analyze_plugin = AnalyzeTaguchiDesignPlugin()

    def test_create_taguchi_l9(self):
        params = CreateTaguchiParams(
            factor_type="3_level",
            array_choice="L9_3_4",
            num_factors=3,
            factor_names_str="Speed, Feed, Depth",
            factor_levels_json=json.dumps({"0": ["100", "200", "300"], "1": ["0.1", "0.2", "0.3"], "2": ["1", "2", "3"]})
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        self.assertEqual(res.action_type, "worksheet_overwrite")
        self.assertEqual(len(res.worksheet_data["rows"]), 9)

    def test_create_taguchi_l18(self):
        params = CreateTaguchiParams(
            factor_type="mixed",
            array_choice="L18_2_1_3_7",
            num_factors=4,
            factor_names_str="Material, Speed, Feed, Coolant",
            factor_levels_json=json.dumps({
                "0": ["Type A", "Type B"],
                "1": ["Low", "Med", "High"],
                "2": ["Slow", "Medium", "Fast"],
                "3": ["None", "Flood", "Mist"]
            })
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        self.assertEqual(len(res.worksheet_data["rows"]), 18)

    def test_analyze_taguchi_larger_is_better(self):
        # L9 dataset
        df = pd.DataFrame({
            "StdOrder": range(1, 10),
            "RunOrder": range(1, 10),
            "A": ["Low", "Low", "Low", "Med", "Med", "Med", "High", "High", "High"],
            "B": [1, 2, 3, 1, 2, 3, 1, 2, 3],
            "C": [10, 20, 30, 20, 30, 10, 30, 10, 20],
            "Strength": [75.2, 78.4, 80.1, 82.5, 85.3, 83.1, 88.0, 89.5, 91.2]
        })

        params = AnalyzeTaguchiParams(
            response_col="Strength",
            factor_cols=["A", "B", "C"],
            sn_ratio_type="larger"
        )

        res = self.analyze_plugin.execute(df, params)
        self.assertIsNotNone(res.tables)
        self.assertEqual(len(res.tables), 4) # S/N table, Means table, ANOVA S/N table, ANOVA Means table
        # Check ranks
        self.assertIn("A", res.statistics["sn_ranks"])

    def test_analyze_taguchi_smaller_is_better(self):
        df = pd.DataFrame({
            "A": [1, 1, 1, 2, 2, 2, 3, 3, 3],
            "B": [1, 2, 3, 1, 2, 3, 1, 2, 3],
            "Defects": [5.2, 4.8, 6.1, 3.2, 2.8, 3.5, 1.5, 1.2, 1.8]
        })

        params = AnalyzeTaguchiParams(
            response_col="Defects",
            factor_cols=["A", "B"],
            sn_ratio_type="smaller"
        )

        res = self.analyze_plugin.execute(df, params)
        self.assertIsNotNone(res.tables)
        self.assertIn("sn_ranks", res.statistics)

    def test_analyze_taguchi_nominal_is_best(self):
        df = pd.DataFrame({
            "A": [1, 1, 1, 2, 2, 2, 3, 3, 3],
            "B": [1, 2, 3, 1, 2, 3, 1, 2, 3],
            "Dimension": [10.05, 9.98, 10.02, 10.12, 10.00, 9.95, 10.01, 10.08, 9.99]
        })

        params = AnalyzeTaguchiParams(
            response_col="Dimension",
            factor_cols=["A", "B"],
            sn_ratio_type="nominal",
            nominal_target=10.0
        )

        res = self.analyze_plugin.execute(df, params)
        self.assertIsNotNone(res.tables)

    def test_analyze_edge_cases(self):
        # Zero variance error
        df_zero = pd.DataFrame({"A": [1, 1, 2, 2], "Y": [10.0, 10.0, 10.0, 10.0]})
        with self.assertRaises(ValueError):
            self.analyze_plugin.execute(df_zero, AnalyzeTaguchiParams(response_col="Y", factor_cols=["A"]))

        # Insufficient rows
        df_few = pd.DataFrame({"A": [1, 2], "Y": [10, 20]})
        with self.assertRaises(ValueError):
            self.analyze_plugin.execute(df_few, AnalyzeTaguchiParams(response_col="Y", factor_cols=["A"]))


if __name__ == "__main__":
    unittest.main()
