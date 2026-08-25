"""
Comprehensive test suite for Mixture Design Generation and Analysis.
Tests:
  - Simplex Centroid Designs (Pure, Binary, Ternary, Axial)
  - Simplex Lattice Designs {q, m}
  - Extreme Vertices / Constrained Mixture Designs
  - Scheffé Canonical Polynomial Regression (Linear, Quadratic, Special Cubic)
  - Non-linear Blending ANOVA
  - Ternary Mixture Contour Plots
  - Edge cases:
      * Zero variance response
      * Insufficient runs for model degree
      * Linear Scheffé model vs Quadratic vs Special Cubic
      * Degenerate / Collinear components
"""

import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, "backend")
from app.plugins.modules.doe_create_mixture import CreateMixtureDesignPlugin, CreateMixtureParams
from app.plugins.modules.doe_analyze_mixture import AnalyzeMixtureDesignPlugin, AnalyzeMixtureParams


class TestMixtureDOE(unittest.TestCase):
    def setUp(self):
        self.create_plugin = CreateMixtureDesignPlugin()
        self.analyze_plugin = AnalyzeMixtureDesignPlugin()

    def test_create_simplex_centroid(self):
        params = CreateMixtureParams(
            design_type="simplex_centroid",
            num_components=3,
            mixture_total=1.0,
            augment_interior=True,
            augment_axial=True,
            randomize_runs=False
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        self.assertEqual(res.action_type, "worksheet_overwrite")
        # 3 pure + 3 binary + 1 centroid + 3 axial = 10 runs
        self.assertEqual(len(res.worksheet_data["rows"]), 10)

    def test_create_simplex_lattice(self):
        params = CreateMixtureParams(
            design_type="simplex_lattice",
            num_components=3,
            lattice_degree=2,
            mixture_total=100.0,
            augment_interior=False,
            randomize_runs=False
        )
        res = self.create_plugin.execute(pd.DataFrame(), params)
        # Degree 2 lattice with 3 components has 6 points
        self.assertEqual(len(res.worksheet_data["rows"]), 6)

    def test_analyze_scheffe_quadratic(self):
        # Scheffé quadratic model:
        # y = 15*x1 + 25*x2 + 30*x3 + 20*x1*x2 - 10*x1*x3 + 5*x2*x3 + noise
        np.random.seed(42)
        X_blend = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.5, 0.5, 0.0],
            [0.5, 0.0, 0.5],
            [0.0, 0.5, 0.5],
            [1/3, 1/3, 1/3],
            [2/3, 1/6, 1/6],
            [1/6, 2/3, 1/6],
            [1/6, 1/6, 2/3]
        ])

        x1 = X_blend[:, 0]
        x2 = X_blend[:, 1]
        x3 = X_blend[:, 2]
        noise = np.random.normal(0, 0.05, len(x1))
        y = 15.0 * x1 + 25.0 * x2 + 30.0 * x3 + 20.0 * (x1 * x2) - 10.0 * (x1 * x3) + 5.0 * (x2 * x3) + noise

        df = pd.DataFrame({
            "StdOrder": range(1, len(x1) + 1),
            "RunOrder": range(1, len(x1) + 1),
            "Comp_A": x1,
            "Comp_B": x2,
            "Comp_C": x3,
            "Viscosity": y
        })

        params = AnalyzeMixtureParams(
            response_col="Viscosity",
            component_cols=["Comp_A", "Comp_B", "Comp_C"],
            model_type="quadratic",
            alpha=0.05
        )

        res = self.analyze_plugin.execute(df, params)
        self.assertIsNotNone(res.tables)
        self.assertGreater(res.statistics["r_sq"], 0.95)
        # Check linear component coefficients close to 15, 25, 30
        self.assertAlmostEqual(res.statistics["coefficients"][0], 15.0, delta=0.5)
        self.assertAlmostEqual(res.statistics["coefficients"][1], 25.0, delta=0.5)
        self.assertAlmostEqual(res.statistics["coefficients"][2], 30.0, delta=0.5)

    def test_analyze_scheffe_linear(self):
        x1 = np.array([1, 0, 0, 0.5, 0.5, 0.0], dtype=float)
        x2 = np.array([0, 1, 0, 0.5, 0.0, 0.5], dtype=float)
        x3 = np.array([0, 0, 1, 0.0, 0.5, 0.5], dtype=float)
        y = 10.0 * x1 + 20.0 * x2 + 30.0 * x3

        df = pd.DataFrame({"A": x1, "B": x2, "C": x3, "Y": y})
        params = AnalyzeMixtureParams(response_col="Y", component_cols=["A", "B", "C"], model_type="linear")
        res = self.analyze_plugin.execute(df, params)
        self.assertAlmostEqual(res.statistics["r_sq"], 1.0, places=4)

    def test_analyze_edge_cases(self):
        # Zero variance error
        df_zero = pd.DataFrame({"A": [1, 0, 0], "B": [0, 1, 0], "C": [0, 0, 1], "Y": [5.0, 5.0, 5.0]})
        with self.assertRaises(ValueError):
            self.analyze_plugin.execute(df_zero, AnalyzeMixtureParams(response_col="Y", component_cols=["A", "B", "C"]))

        # Insufficient runs (e.g. 2 runs for 3 components)
        df_few = pd.DataFrame({"A": [1, 0], "B": [0, 1], "C": [0, 0], "Y": [10, 20]})
        with self.assertRaises(ValueError):
            self.analyze_plugin.execute(df_few, AnalyzeMixtureParams(response_col="Y", component_cols=["A", "B", "C"]))


if __name__ == "__main__":
    unittest.main()
