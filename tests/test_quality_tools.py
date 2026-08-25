"""
Comprehensive test suite for OpenMinitab Quality Tools module.
Tests all 13 modules:
  1. Run Chart (run_chart)
  2. Pareto Chart (pareto_chart)
  3. Cause-and-Effect Diagram (cause_and_effect)
  4. Individual Distribution Identification (distribution_id)
  5. Johnson Transformation (johnson_transformation)
  6. Process Capability Analysis (process_capability)
  7. Capability Sixpack (capability_sixpack)
  8. Tolerance Intervals (tolerance_intervals)
  9. Gage R&R Study (gage_rr)
  10. Attribute Agreement Analysis (attribute_agreement)
  11. Acceptance Sampling by Attributes & Variables (acceptance_sampling)
  12. Multi-Vari Chart (multi_vari)
  13. Symmetry Plot (symmetry_plot)
"""

import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, "backend")
from app.plugins.modules.quality_tools.run_chart import RunChartPlugin, RunChartParams
from app.plugins.modules.quality_tools.pareto_chart import ParetoChartPlugin, ParetoChartParams
from app.plugins.modules.quality_tools.cause_and_effect import CauseAndEffectPlugin, CauseAndEffectParams
from app.plugins.modules.quality_tools.distribution_id import DistributionIdPlugin, DistributionIdParams
from app.plugins.modules.quality_tools.johnson_transformation import JohnsonTransformationPlugin, JohnsonTransformationParams
from app.plugins.modules.quality_tools.process_capability import ProcessCapabilityPlugin, ProcessCapabilityParams
from app.plugins.modules.quality_tools.capability_sixpack import CapabilitySixpackPlugin, CapabilitySixpackParams
from app.plugins.modules.quality_tools.tolerance_intervals import ToleranceIntervalsPlugin, ToleranceIntervalsParams
from app.plugins.modules.quality_tools.gage_rr import GageRrPlugin, GageRrParams
from app.plugins.modules.quality_tools.attribute_agreement import AttributeAgreementPlugin, AttributeAgreementParams
from app.plugins.modules.quality_tools.acceptance_sampling import AcceptanceSamplingPlugin, AcceptanceSamplingParams
from app.plugins.modules.quality_tools.multi_vari import MultiVariPlugin, MultiVariParams
from app.plugins.modules.quality_tools.symmetry_plot import SymmetryPlotPlugin, SymmetryPlotParams


class TestQualityToolsSuite(unittest.TestCase):

    def test_run_chart(self):
        plugin = RunChartPlugin()
        df = pd.DataFrame({"Diam": [10.2, 10.5, 9.8, 10.1, 10.3, 9.9, 10.4, 10.0, 10.6, 9.7, 10.2, 10.1]})
        res = plugin.execute(df, RunChartParams(data_column="Diam", subgroup_size=1, reference_type="median"))
        self.assertIsNotNone(res.tables)
        self.assertIn("runs_med_obs", res.statistics)
        self.assertIn("p_clustering", res.statistics)
        self.assertIsNotNone(res.plotly_figure)

    def test_pareto_chart(self):
        plugin = ParetoChartPlugin()
        df = pd.DataFrame({
            "Defect": ["Scratches", "Dents", "Burrs", "Contamination", "Discoloration", "Other Minor", "Loose Parts"],
            "Count": [85, 42, 28, 15, 8, 4, 2]
        })
        res = plugin.execute(df, ParetoChartParams(defects_column="Defect", frequencies_column="Count", combine_threshold=90.0))
        self.assertIsNotNone(res.tables)
        self.assertEqual(res.statistics["top_category"], "Scratches")
        self.assertGreater(res.statistics["top_category_pct"], 40.0)

    def test_cause_and_effect(self):
        plugin = CauseAndEffectPlugin()
        res = plugin.execute(pd.DataFrame(), CauseAndEffectParams(effect_label="Surface Roughness"))
        self.assertIsNotNone(res.plotly_figure)
        self.assertEqual(res.statistics["effect"], "Surface Roughness")
        self.assertGreater(res.statistics["total_causes"], 10)

    def test_distribution_id(self):
        plugin = DistributionIdPlugin()
        np.random.seed(42)
        data = np.random.normal(50, 5, 40)
        df = pd.DataFrame({"Thickness": data})
        res = plugin.execute(df, DistributionIdParams(data_column="Thickness"))
        self.assertIsNotNone(res.tables)
        self.assertIn("best_distribution", res.statistics)
        self.assertGreater(res.statistics["best_p_val"], 0.05)

    def test_johnson_transformation(self):
        plugin = JohnsonTransformationPlugin()
        np.random.seed(42)
        # Skewed gamma data
        data = np.random.gamma(2.0, 2.0, 50)
        df = pd.DataFrame({"Yield": data})
        res = plugin.execute(df, JohnsonTransformationParams(data_column="Yield", p_value_to_select=0.10))
        self.assertIsNotNone(res.tables)
        self.assertIn("selected_family", res.statistics)
        self.assertIsNotNone(res.plotly_figure)

    def test_process_capability(self):
        plugin = ProcessCapabilityPlugin()
        np.random.seed(42)
        data = np.random.normal(100.0, 2.0, 50)
        df = pd.DataFrame({"Dimension": data})
        params = ProcessCapabilityParams(
            data_column="Dimension",
            lsl=94.0,
            usl=106.0,
            target=100.0,
            subgroup_size=5
        )
        res = plugin.execute(df, params)
        self.assertIsNotNone(res.tables)
        self.assertGreater(res.statistics["cpk"], 0.8)
        self.assertGreater(res.statistics["ppk"], 0.8)

    def test_capability_sixpack(self):
        plugin = CapabilitySixpackPlugin()
        np.random.seed(42)
        data = np.random.normal(25.0, 0.5, 60)
        df = pd.DataFrame({"Weight": data})
        params = CapabilitySixpackParams(data_column="Weight", lsl=23.0, usl=27.0, subgroup_size=5)
        res = plugin.execute(df, params)
        self.assertIsNotNone(res.plotly_figure)
        self.assertGreaterEqual(len(res.plotly_figure["data"]), 6)

    def test_tolerance_intervals(self):
        plugin = ToleranceIntervalsPlugin()
        np.random.seed(42)
        data = np.random.normal(15.0, 1.0, 30)
        df = pd.DataFrame({"Strength": data})
        res = plugin.execute(df, ToleranceIntervalsParams(data_column="Strength", coverage_percent=90.0, confidence_level=95.0))
        self.assertIsNotNone(res.tables)
        self.assertLess(res.statistics["lower_tol_normal"], 15.0)
        self.assertGreater(res.statistics["upper_tol_normal"], 15.0)

    def test_gage_rr(self):
        plugin = GageRrPlugin()
        # 10 parts, 3 operators, 2 replicates = 60 measurements
        np.random.seed(42)
        parts = np.repeat(range(1, 11), 6)
        ops = np.tile(np.repeat(["Op1", "Op2", "Op3"], 2), 10)
        meas = parts * 5.0 + np.random.normal(0, 0.2, 60)
        df = pd.DataFrame({"Part": parts, "Operator": ops, "Measurement": meas})
        params = GageRrParams(part_column="Part", operator_column="Operator", measurement_column="Measurement", tolerance=10.0)
        res = plugin.execute(df, params)
        self.assertIsNotNone(res.tables)
        self.assertIn("pct_sv_gage_rr", res.statistics)
        self.assertGreaterEqual(res.statistics["ndc"], 1)

    def test_attribute_agreement(self):
        plugin = AttributeAgreementPlugin()
        df = pd.DataFrame({
            "Sample": [1, 1, 2, 2, 3, 3, 4, 4, 5, 5] * 2,
            "Appraiser": ["A"] * 10 + ["B"] * 10,
            "Rating": ["Pass", "Pass", "Fail", "Fail", "Pass", "Pass", "Fail", "Fail", "Pass", "Pass"] * 2,
            "Standard": ["Pass", "Pass", "Fail", "Fail", "Pass", "Pass", "Fail", "Fail", "Pass", "Pass"] * 2
        })
        params = AttributeAgreementParams(
            attribute_column="Rating",
            sample_column="Sample",
            appraiser_column="Appraiser",
            standard_reference_column="Standard"
        )
        res = plugin.execute(df, params)
        self.assertIsNotNone(res.tables)
        self.assertEqual(res.statistics["kappa"], 1.0)

    def test_acceptance_sampling(self):
        plugin = AcceptanceSamplingPlugin()
        # Attributes
        res_attr = plugin.execute(pd.DataFrame(), AcceptanceSamplingParams(measurement_type="attributes", aql=1.0, rql=5.0, lot_size=5000))
        self.assertIsNotNone(res_attr.plotly_figure)
        self.assertGreater(res_attr.statistics["sample_size_n"], 10)

        # Variables
        res_var = plugin.execute(pd.DataFrame(), AcceptanceSamplingParams(measurement_type="variables", aql=1.0, rql=4.0, lot_size=5000))
        self.assertIsNotNone(res_var.plotly_figure)
        self.assertGreater(res_var.statistics["sample_size_n"], 5)

    def test_multi_vari(self):
        plugin = MultiVariPlugin()
        df = pd.DataFrame({
            "Resp": [10.2, 10.5, 9.8, 10.1, 11.2, 11.5, 10.8, 11.0],
            "Pos": ["Top", "Bot", "Top", "Bot", "Top", "Bot", "Top", "Bot"],
            "Batch": ["B1", "B1", "B1", "B1", "B2", "B2", "B2", "B2"]
        })
        res = plugin.execute(df, MultiVariParams(response_column="Resp", factor_1="Pos", factor_2="Batch"))
        self.assertIsNotNone(res.tables)
        self.assertEqual(res.statistics["num_cells"], 4)

    def test_symmetry_plot(self):
        plugin = SymmetryPlotPlugin()
        df = pd.DataFrame({"Val": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]})
        res = plugin.execute(df, SymmetryPlotParams(data_column="Val"))
        self.assertIsNotNone(res.tables)
        self.assertAlmostEqual(res.statistics["median"], 5.0)
        self.assertAlmostEqual(res.statistics["skewness"], 0.0, places=2)


if __name__ == "__main__":
    unittest.main()
