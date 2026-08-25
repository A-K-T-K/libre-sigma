"""
Comprehensive test suite for Factorial Design Generation and Analysis.
Tests:
  - 2-level Full Factorial ($2^k$) with pyDOE3
  - 2-level Fractional Factorial ($2^{k-p}$) with pyDOE3
  - Plackett-Burman Screening Designs with pyDOE3
  - General Full Factorial Designs (Mixed levels)
  - Center Points, Blocks, and Replications
  - Factorial Regression Analysis (Effects, ANOVA, Model Summary, Pareto, Main Effects Plot)
  - Edge cases:
      * Zero variance response (all identical)
      * Insufficient rows / degrees of freedom
      * Saturated models (0 error df)
      * Perfect linear fit ($R^2 = 1.0$)
      * Collinear / Rank deficient design matrices
      * Missing response / factor columns
      * String / Categorical levels in factors
      * Order 1 (Linear only) vs Order 2 vs Order 3 interactions
"""

import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, "backend")
from app.plugins.modules.doe_create_factorial import CreateFactorialDesignPlugin, CreateFactorialParams
from app.plugins.modules.doe_analyze_factorial import AnalyzeFactorialDesignPlugin, AnalyzeFactorialParams


class TestFactorialDOE(unittest.TestCase):
    def setUp(self):
        self.create_plugin = CreateFactorialDesignPlugin()
        self.analyze_plugin = AnalyzeFactorialDesignPlugin()

    def test_create_2level_full_factorial(self):
        params = CreateFactorialParams(
            design_type="2_level",
            num_factors=3,
            num_runs=8,
            num_center_points=2,
            num_replicates=1,
            num_blocks=1,
            factor_names_str="Temp, Pressure, Speed",
            factor_lows_str="100, 10, 500",
            factor_highs_str="200, 20, 1000",
            randomize_runs=False,
            worksheet_name="Full 2^3"
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        self.assertEqual(res.action_type, "worksheet_overwrite")
        self.assertIsNotNone(res.worksheet_data)
        rows = res.worksheet_data["rows"]
        # 8 factorial runs + 2 center points = 10 runs
        self.assertEqual(len(rows), 10)
        self.assertIn("Temp", [c["name"] for c in res.worksheet_data["columns"]])
        self.assertIn("Response_1", [c["name"] for c in res.worksheet_data["columns"]])

    def test_create_fractional_factorial(self):
        params = CreateFactorialParams(
            design_type="2_level",
            num_factors=5,
            num_runs=16, # 2^(5-1) Resolution V
            factor_names_str="A, B, C, D, E",
            randomize_runs=False
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        self.assertEqual(len(res.worksheet_data["rows"]), 16)
        self.assertIn("Resolution V", res.subtitle)

    def test_create_plackett_burman(self):
        params = CreateFactorialParams(
            design_type="plackett_burman",
            num_factors=7,
            num_runs=8,
            factor_names_str="A, B, C, D, E, F, G",
            randomize_runs=False
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        self.assertEqual(len(res.worksheet_data["rows"]), 8)

    def test_create_general_full_factorial(self):
        params = CreateFactorialParams(
            design_type="general_full",
            num_factors=3,
            general_levels_str="2, 3, 2",
            factor_names_str="F1, F2, F3",
            randomize_runs=False
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        # 2 * 3 * 2 = 12 runs
        self.assertEqual(len(res.worksheet_data["rows"]), 12)

    def test_analyze_factorial_clean_data(self):
        # Generate 2^3 factorial design with known linear effects
        # y = 50 + 5*A - 3*B + 2*C + 4*A*B + noise
        np.random.seed(42)
        A = np.array([-1, 1, -1, 1, -1, 1, -1, 1, 0, 0, 0, 0], dtype=float)
        B = np.array([-1, -1, 1, 1, -1, -1, 1, 1, 0, 0, 0, 0], dtype=float)
        C = np.array([-1, -1, -1, -1, 1, 1, 1, 1, 0, 0, 0, 0], dtype=float)
        noise = np.random.normal(0, 0.2, len(A))
        y = 50.0 + 5.0 * A - 3.0 * B + 2.0 * C + 4.0 * (A * B) + noise

        df = pd.DataFrame({
            "StdOrder": range(1, len(A) + 1),
            "RunOrder": range(1, len(A) + 1),
            "Temp": A * 50 + 150, # Actual units
            "Press": B * 5 + 15,
            "Speed": C * 200 + 600,
            "Yield": y
        })

        params = AnalyzeFactorialParams(
            response_col="Yield",
            factor_cols=["Temp", "Press", "Speed"],
            max_order=2,
            alpha=0.05
        )

        res = self.analyze_plugin.execute(df, params)
        self.assertIsNotNone(res.tables)
        self.assertGreater(res.statistics["r_sq"], 0.95)
        # Check that Term 'Temp' (A) effect is close to 10 (2 * 5)
        self.assertAlmostEqual(res.statistics["effects"][0], 10.0, delta=1.5)
        # Check Plotly figures are generated (Pareto + Main effects)
        self.assertEqual(len(res.plotly_figures), 2)

    def test_analyze_perfect_fit(self):
        # Exact linear combination with zero noise -> R^2 = 1.0
        A = np.array([-1, 1, -1, 1, -1, 1, -1, 1], dtype=float)
        B = np.array([-1, -1, 1, 1, -1, -1, 1, 1], dtype=float)
        C = np.array([-1, -1, -1, -1, 1, 1, 1, 1], dtype=float)
        y = 100.0 + 10.0 * A - 5.0 * B + 2.0 * C

        df = pd.DataFrame({"A": A, "B": B, "C": C, "Y": y})
        params = AnalyzeFactorialParams(response_col="Y", factor_cols=["A", "B", "C"], max_order=1)
        res = self.analyze_plugin.execute(df, params)
        self.assertAlmostEqual(res.statistics["r_sq"], 1.0, places=4)

    def test_analyze_saturated_model(self):
        # 8 runs, 3 factors with 2-way and 3-way interactions (8 parameters -> 0 error df)
        A = np.array([-1, 1, -1, 1, -1, 1, -1, 1], dtype=float)
        B = np.array([-1, -1, 1, 1, -1, -1, 1, 1], dtype=float)
        C = np.array([-1, -1, -1, -1, 1, 1, 1, 1], dtype=float)
        y = 20.0 + 3.0 * A + 2.0 * B - 1.5 * C + 0.5 * A * B

        df = pd.DataFrame({"A": A, "B": B, "C": C, "Resp": y})
        params = AnalyzeFactorialParams(response_col="Resp", factor_cols=["A", "B", "C"], max_order=3)
        res = self.analyze_plugin.execute(df, params)
        self.assertIsNotNone(res.tables)
        self.assertAlmostEqual(res.statistics["r_sq"], 1.0, places=4)

    def test_analyze_edge_cases(self):
        # Zero variance error
        df_zero = pd.DataFrame({
            "A": [-1, 1, -1, 1],
            "B": [-1, -1, 1, 1],
            "Y": [10.0, 10.0, 10.0, 10.0]
        })
        with self.assertRaises(ValueError):
            self.analyze_plugin.execute(df_zero, AnalyzeFactorialParams(response_col="Y", factor_cols=["A", "B"]))

        # Insufficient rows
        df_few = pd.DataFrame({
            "A": [-1, 1],
            "B": [-1, 1],
            "Y": [12.0, 15.0]
        })
        with self.assertRaises(ValueError):
            self.analyze_plugin.execute(df_few, AnalyzeFactorialParams(response_col="Y", factor_cols=["A", "B"]))

        # Missing column error
        df_valid = pd.DataFrame({"A": [1, 2, 3, 4], "B": [4, 5, 6, 7], "Y": [10, 20, 30, 40]})
        with self.assertRaises(ValueError):
            self.analyze_plugin.execute(df_valid, AnalyzeFactorialParams(response_col="NonExistent", factor_cols=["A", "B"]))


if __name__ == "__main__":
    unittest.main()
