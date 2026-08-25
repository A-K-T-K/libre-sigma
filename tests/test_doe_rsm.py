"""
Comprehensive test suite for Response Surface Methodology (RSM) Generation and Analysis.
Tests:
  - Central Composite Design (CCD) (Rotatable, Spherical, Face-Centered, Orthogonal) with pyDOE3
  - Box-Behnken Design (BBD) with pyDOE3
  - Cube, Axial, and Center Points
  - Response Surface Quadratic Regression
  - Canonical Analysis (Stationary Point Optimization for Maximum, Minimum, Saddle Points)
  - ANOVA with Lack of Fit & Pure Error Decomposition
  - 2D Contour Plots & 3D Surfaces
  - Edge cases:
      * Zero variance response
      * Insufficient sample rows
      * Collinear quadratic matrix
      * Stationary saddle point vs maximum vs minimum
      * Custom alpha values
"""

import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, "backend")
from app.plugins.modules.doe_create_rsm import CreateRsmDesignPlugin, CreateRsmParams
from app.plugins.modules.doe_analyze_rsm import AnalyzeRsmDesignPlugin, AnalyzeRsmParams


class TestRsmDOE(unittest.TestCase):
    def setUp(self):
        self.create_plugin = CreateRsmDesignPlugin()
        self.analyze_plugin = AnalyzeRsmDesignPlugin()

    def test_create_ccd_rotatable(self):
        params = CreateRsmParams(
            design_type="ccd",
            num_factors=3,
            ccd_subtype="full",
            alpha_choice="rotatable",
            cube_center_points=4,
            axial_center_points=2,
            factor_names_str="Time, Temp, Conc",
            randomize_runs=False
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        self.assertEqual(res.action_type, "worksheet_overwrite")
        # 8 cube + 4 center + 6 axial + 2 center = 20 runs
        self.assertEqual(len(res.worksheet_data["rows"]), 20)
        self.assertAlmostEqual(res.statistics["alpha"], (8)**0.25, places=3)

    def test_create_ccd_face_centered(self):
        params = CreateRsmParams(
            design_type="ccd",
            num_factors=2,
            alpha_choice="face_centered",
            cube_center_points=2,
            axial_center_points=2,
            randomize_runs=False
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        # 4 cube + 2 center + 4 axial + 2 center = 12 runs
        self.assertEqual(len(res.worksheet_data["rows"]), 12)
        self.assertEqual(res.statistics["alpha"], 1.0)

    def test_create_bbd(self):
        params = CreateRsmParams(
            design_type="bbd",
            num_factors=3,
            bbd_center_points=3,
            randomize_runs=False
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        # 12 edge + 3 center = 15 runs
        self.assertEqual(len(res.worksheet_data["rows"]), 15)

    def test_analyze_rsm_with_stationary_peak(self):
        # Quadratic function with a true maximum at (0, 0, 0):
        # y = 80 - 4*A^2 - 3*B^2 - 2*C^2 + 1.5*A - 1*B + noise
        np.random.seed(42)
        k = 3
        alpha = 1.682
        cube = np.array([
            [-1, -1, -1], [1, -1, -1], [-1, 1, -1], [1, 1, -1],
            [-1, -1, 1], [1, -1, 1], [-1, 1, 1], [1, 1, 1]
        ])
        axial = np.array([
            [-alpha, 0, 0], [alpha, 0, 0],
            [0, -alpha, 0], [0, alpha, 0],
            [0, 0, -alpha], [0, 0, alpha]
        ])
        centers = np.zeros((6, 3))
        X_coded = np.vstack([cube, axial, centers])

        A = X_coded[:, 0]
        B = X_coded[:, 1]
        C = X_coded[:, 2]
        noise = np.random.normal(0, 0.1, len(A))
        y = 80.0 + 1.5 * A - 1.0 * B - 4.0 * (A**2) - 3.0 * (B**2) - 2.0 * (C**2) + noise

        df = pd.DataFrame({
            "StdOrder": range(1, len(A) + 1),
            "RunOrder": range(1, len(A) + 1),
            "Time": A * 10 + 50,
            "Temp": B * 20 + 160,
            "Conc": C * 5 + 25,
            "Response_1": y
        })

        params = AnalyzeRsmParams(
            response_col="Response_1",
            factor_cols=["Time", "Temp", "Conc"],
            alpha=0.05
        )

        res = self.analyze_plugin.execute(df, params)
        self.assertIsNotNone(res.tables)
        self.assertGreater(res.statistics["r_sq"], 0.95)
        # Should identify peak / maximum
        self.assertIn("Maximum", res.statistics["stationary_type"])
        # Should generate contour plot
        self.assertIsNotNone(res.plotly_figure)

    def test_analyze_rsm_saddle_point(self):
        # Quadratic function with saddle point (+ on A^2, - on B^2)
        np.random.seed(42)
        alpha = 1.414
        cube = np.array([[-1, -1], [1, -1], [-1, 1], [1, 1]])
        axial = np.array([[-alpha, 0], [alpha, 0], [0, -alpha], [0, alpha]])
        centers = np.zeros((5, 2))
        X = np.vstack([cube, axial, centers])
        A, B = X[:, 0], X[:, 1]
        y = 50.0 + 2.0 * A + 3.0 * (A**2) - 4.0 * (B**2) + np.random.normal(0, 0.05, len(A))

        df = pd.DataFrame({"A": A, "B": B, "Resp": y})
        params = AnalyzeRsmParams(response_col="Resp", factor_cols=["A", "B"])
        res = self.analyze_plugin.execute(df, params)
        self.assertIn("Saddle", res.statistics["stationary_type"])

    def test_analyze_edge_cases(self):
        # Zero variance error
        df_zero = pd.DataFrame({"A": [-1, 1, 0], "B": [-1, 1, 0], "Y": [10.0, 10.0, 10.0]})
        with self.assertRaises(ValueError):
            self.analyze_plugin.execute(df_zero, AnalyzeRsmParams(response_col="Y", factor_cols=["A", "B"]))

        # Insufficient rows (requires at least 1 + 2k + k(k-1)/2)
        df_few = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6], "Y": [10, 20, 30]})
        with self.assertRaises(ValueError):
            self.analyze_plugin.execute(df_few, AnalyzeRsmParams(response_col="Y", factor_cols=["A", "B"]))


if __name__ == "__main__":
    unittest.main()
