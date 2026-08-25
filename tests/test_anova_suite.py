"""
Unit tests for the complete Master ANOVA Suite (9 Modules).
Tests pure Python statistical compute engines, formulas, unbiasing constants, and edge cases.
"""

import unittest
import os
import sys
import numpy as np
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.app.plugins.modules.anova.one_way_anova import OneWayAnovaPlugin, OneWayAnovaParams
from backend.app.plugins.modules.anova.anom import AnomPlugin, AnomParams
from backend.app.plugins.modules.anova.balanced_anova import BalancedAnovaPlugin, BalancedAnovaParams
from backend.app.plugins.modules.anova.general_linear_model import GeneralLinearModelPlugin, GlmParams
from backend.app.plugins.modules.anova.mixed_effects_model import MixedEffectsPlugin, MixedEffectsParams
from backend.app.plugins.modules.anova.fully_nested_anova import FullyNestedAnovaPlugin, FullyNestedAnovaParams
from backend.app.plugins.modules.anova.general_manova import GeneralManovaPlugin, ManovaParams
from backend.app.plugins.modules.anova.test_equal_variances import TestEqualVariancesPlugin, EqualVariancesParams
from backend.app.plugins.modules.anova.factorial_plots import (
    MainEffectsPlotPlugin, MainEffectsPlotParams,
    InteractionPlotPlugin, InteractionPlotParams,
    IntervalPlotPlugin, IntervalPlotParams
)


class TestMasterAnovaSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        np.random.seed(42)
        # Synthetic Balanced / Factorial Dataset (3 Fertilizer x 2 Water x 2 Reps = 12 obs)
        cls.df_anova = pd.DataFrame({
            "Yield": [25.0, 26.0, 27.5, 28.5, 32.0, 33.0, 34.5, 35.5, 40.0, 41.0, 42.5, 43.5],
            "Fertilizer": ["Low", "Low", "Low", "Low", "Med", "Med", "Med", "Med", "High", "High", "High", "High"],
            "Water": ["Dry", "Dry", "Wet", "Wet", "Dry", "Dry", "Wet", "Wet", "Dry", "Dry", "Wet", "Wet"],
            "Biomass": [12.0, 13.0, 14.5, 15.5, 18.0, 19.0, 20.5, 21.5, 24.0, 25.0, 26.5, 27.5],
            "Subject": ["S1", "S1", "S2", "S2", "S3", "S3", "S4", "S4", "S5", "S5", "S6", "S6"],
            "Batch": ["B1", "B1", "B1", "B1", "B1", "B1", "B2", "B2", "B2", "B2", "B2", "B2"],
            "Sample": ["Sm1", "Sm1", "Sm2", "Sm2", "Sm3", "Sm3", "Sm4", "Sm4", "Sm5", "Sm5", "Sm6", "Sm6"],
            "Run": [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2],
            "Covariate": [10.2, 11.1, 12.0, 12.8, 14.5, 15.2, 16.1, 16.9, 20.1, 21.0, 22.0, 22.8]
        })

    def test_01_one_way_anova(self):
        plugin = OneWayAnovaPlugin()
        params = OneWayAnovaParams(
            response_column="Yield",
            factor_column="Fertilizer",
            assume_equal_variances=True,
            post_hoc_method="tukey"
        )
        res = plugin.execute(self.df_anova, params)
        self.assertIn("F =", res.subtitle)
        self.assertGreater(res.statistics["f_stat"], 50.0)
        self.assertLess(res.statistics["p_value"], 0.001)
        self.assertIn("groupings", res.statistics)
        self.assertEqual(len(res.tables), 4)

    def test_02_anom(self):
        plugin = AnomPlugin()
        params = AnomParams(
            response_column="Yield",
            factor_1="Fertilizer",
            distribution_type="normal",
            alpha=0.05
        )
        res = plugin.execute(self.df_anova, params)
        self.assertGreater(res.statistics["udl"], res.statistics["grand_mean"])
        self.assertLess(res.statistics["ldl"], res.statistics["grand_mean"])
        self.assertGreater(res.statistics["out_of_limits"], 0)

    def test_03_balanced_anova(self):
        plugin = BalancedAnovaPlugin()
        params = BalancedAnovaParams(
            response_column="Yield",
            factors=["Fertilizer", "Water"],
            random_factors=["Fertilizer"]
        )
        res = plugin.execute(self.df_anova, params)
        self.assertIn("Balanced ANOVA", res.title)
        self.assertTrue(res.statistics["is_balanced"])
        self.assertGreater(res.statistics["ms_error"], 0)

    def test_04_general_linear_model(self):
        plugin = GeneralLinearModelPlugin()
        params = GlmParams(
            response_column="Yield",
            factors=["Fertilizer"],
            covariates=["Covariate"],
            ss_type="type3"
        )
        res = plugin.execute(self.df_anova, params)
        self.assertGreater(res.statistics["r_sq"], 0.90)
        self.assertIn("ls_means", res.statistics)
        self.assertEqual(len(res.statistics["ls_means"]), 3)

    def test_05_mixed_effects_model(self):
        plugin = MixedEffectsPlugin()
        params = MixedEffectsParams(
            response_column="Yield",
            fixed_factors=["Covariate"],
            group_column="Subject"
        )
        res = plugin.execute(self.df_anova, params)
        self.assertGreater(res.statistics["var_residual"], 0)
        self.assertIn("icc", res.statistics)
        self.assertEqual(res.statistics["num_groups"], 6)

    def test_06_fully_nested_anova(self):
        plugin = FullyNestedAnovaPlugin()
        params = FullyNestedAnovaParams(
            response_column="Yield",
            nested_hierarchy=["Batch", "Sample"]
        )
        res = plugin.execute(self.df_anova, params)
        self.assertIn("variance_components", res.statistics)
        self.assertIn("pct_variance", res.statistics)
        self.assertAlmostEqual(sum(res.statistics["pct_variance"].values()), 100.0, places=1)

    def test_07_general_manova(self):
        plugin = GeneralManovaPlugin()
        params = ManovaParams(
            response_columns=["Yield", "Biomass"],
            factor_column="Fertilizer"
        )
        res = plugin.execute(self.df_anova, params)
        self.assertLess(res.statistics["wilks_lambda"], 0.05)
        self.assertLess(res.statistics["wilks_p"], 0.001)
        self.assertGreater(res.statistics["pillai_trace"], 0)

    def test_08_test_equal_variances(self):
        plugin = TestEqualVariancesPlugin()
        params = EqualVariancesParams(
            response_column="Yield",
            factor_column="Fertilizer",
            confidence_level=95.0
        )
        res = plugin.execute(self.df_anova, params)
        self.assertIn("bartlett_p", res.statistics)
        self.assertIn("levene_p", res.statistics)
        self.assertIn("brown_forsythe_p", res.statistics)

    def test_09_factorial_plots(self):
        # 1. Main Effects
        p1 = MainEffectsPlotPlugin()
        res1 = p1.execute(self.df_anova, MainEffectsPlotParams(response_column="Yield", factors=["Fertilizer", "Water"]))
        self.assertEqual(res1.statistics["num_factors"], 2)

        # 2. Interaction Plot
        p2 = InteractionPlotPlugin()
        res2 = p2.execute(self.df_anova, InteractionPlotParams(response_column="Yield", factor_x="Fertilizer", factor_trace="Water"))
        self.assertEqual(len(res2.statistics["x_levels"]), 3)

        # 3. Interval Plot
        p3 = IntervalPlotPlugin()
        res3 = p3.execute(self.df_anova, IntervalPlotParams(response_column="Yield", factor_column="Fertilizer", confidence_level=95.0))
        self.assertEqual(len(res3.statistics["group_means"]), 3)


if __name__ == "__main__":
    unittest.main()
