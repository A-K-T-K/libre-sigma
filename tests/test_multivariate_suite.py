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

from backend.app.plugins.modules.multivariate.pca import PrincipalComponentAnalysisPlugin, PcaParams
from backend.app.plugins.modules.multivariate.factor_analysis import FactorAnalysisPlugin, FactorAnalysisParams
from backend.app.plugins.modules.multivariate.item_analysis import ItemAnalysisPlugin, ItemAnalysisParams
from backend.app.plugins.modules.multivariate.cluster_observations import ClusterObservationsPlugin, ClusterObsParams
from backend.app.plugins.modules.multivariate.cluster_variables import ClusterVariablesPlugin, ClusterVarsParams
from backend.app.plugins.modules.multivariate.cluster_kmeans import ClusterKMeansPlugin, ClusterKMeansParams
from backend.app.plugins.modules.multivariate.discriminant_analysis import DiscriminantAnalysisPlugin, DiscriminantParams
from backend.app.plugins.modules.multivariate.correspondence_analysis import CorrespondenceAnalysisPlugin, CorrespondenceParams


class TestMultivariateSuite(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        n = 30
        # Synthetic multivariate dataset
        self.df = pd.DataFrame({
            "Yield": np.random.normal(85, 5, n),
            "Temperature": np.random.normal(150, 10, n),
            "Pressure": np.random.normal(30, 3, n),
            "Viscosity": np.random.normal(45, 8, n),
            "Operator": np.random.choice(["OpA", "OpB", "OpC"], n),
            "Shift": np.random.choice(["Morning", "Evening"], n),
            "Item1": np.random.randint(1, 6, n),
            "Item2": np.random.randint(1, 6, n),
            "Item3": np.random.randint(1, 6, n),
            "Item4": np.random.randint(1, 6, n),
        })

    def test_pca_correlation_and_storage(self):
        plugin = PrincipalComponentAnalysisPlugin()
        params = PcaParams(
            variables=["Yield", "Temperature", "Pressure", "Viscosity"],
            matrix_type="Correlation Matrix",
            storage_options=True
        )
        res = plugin.execute(self.df, params)
        self.assertIn("Principal Component Analysis", res.title)
        self.assertEqual(len(res.tables), 2)
        self.assertIsNotNone(res.plotly_figure)
        self.assertEqual(res.action_type, "worksheet_append_columns")
        self.assertIsNotNone(res.worksheet_data)
        self.assertGreaterEqual(len(res.worksheet_data["columns"]), 1)
        self.assertAlmostEqual(res.statistics["cumulative"][-1], 1.0, places=4)

    def test_pca_covariance(self):
        plugin = PrincipalComponentAnalysisPlugin()
        params = PcaParams(
            variables=["Yield", "Temperature", "Pressure"],
            matrix_type="Covariance Matrix",
            num_components_to_extract=2
        )
        res = plugin.execute(self.df, params)
        self.assertIn("Covariance Matrix", res.statistics["matrix_type"])
        self.assertEqual(res.statistics["num_components_extracted"], 2)

    def test_factor_analysis(self):
        plugin = FactorAnalysisPlugin()
        params = FactorAnalysisParams(
            variables=["Yield", "Temperature", "Pressure", "Viscosity"],
            num_factors=2,
            rotation_method="Varimax (Orthogonal)",
            storage_options=True
        )
        res = plugin.execute(self.df, params)
        self.assertIn("Factor Analysis", res.title)
        self.assertEqual(len(res.tables), 2)
        self.assertIsNotNone(res.plotly_figure)
        self.assertEqual(res.statistics["num_factors"], 2)
        self.assertEqual(res.action_type, "worksheet_append_columns")

    def test_item_analysis_cronbach_alpha(self):
        plugin = ItemAnalysisPlugin()
        params = ItemAnalysisParams(
            item_variables=["Item1", "Item2", "Item3", "Item4"],
            storage_options=True
        )
        res = plugin.execute(self.df, params)
        self.assertIn("Item Analysis", res.title)
        self.assertEqual(len(res.tables), 2)
        self.assertIn("cronbach_alpha", res.statistics)
        self.assertEqual(len(res.statistics["omitted_alphas"]), 4)
        self.assertEqual(res.action_type, "worksheet_append_columns")

    def test_cluster_observations(self):
        plugin = ClusterObservationsPlugin()
        params = ClusterObsParams(
            variables=["Yield", "Temperature", "Pressure"],
            linkage_method="Average",
            distance_metric="Euclidean",
            num_clusters=3,
            storage_options=True
        )
        res = plugin.execute(self.df, params)
        self.assertIn("Hierarchical Cluster", res.title)
        self.assertEqual(len(res.tables), 2)
        self.assertIsNotNone(res.plotly_figure)
        self.assertEqual(res.action_type, "worksheet_append_columns")
        self.assertEqual(len(res.worksheet_data["rows"]), len(self.df))

    def test_cluster_variables(self):
        plugin = ClusterVariablesPlugin()
        params = ClusterVarsParams(
            variables=["Yield", "Temperature", "Pressure", "Viscosity"],
            linkage_method="Ward",
            distance_metric="Correlation (1 - r)",
            num_clusters=2
        )
        res = plugin.execute(self.df, params)
        self.assertIn("Hierarchical Clustering of Variables", res.title)
        self.assertEqual(len(res.tables), 2)
        self.assertIsNotNone(res.plotly_figure)
        self.assertEqual(len(res.statistics["cluster_assignments"]), 4)

    def test_cluster_kmeans(self):
        plugin = ClusterKMeansPlugin()
        params = ClusterKMeansParams(
            variables=["Yield", "Temperature", "Pressure", "Viscosity"],
            number_of_clusters=3,
            standardize=True,
            storage_options=True
        )
        res = plugin.execute(self.df, params)
        self.assertIn("K-Means", res.title)
        self.assertEqual(len(res.tables), 3)
        self.assertGreater(res.statistics["ss_total"], 0)
        self.assertEqual(res.action_type, "worksheet_append_columns")

    def test_discriminant_analysis_lda(self):
        plugin = DiscriminantAnalysisPlugin()
        params = DiscriminantParams(
            group_variable="Operator",
            predictors=["Yield", "Temperature", "Pressure"],
            discriminant_function="Linear (LDA)",
            cross_validation=True,
            storage_options=True
        )
        res = plugin.execute(self.df, params)
        self.assertIn("Discriminant Analysis", res.title)
        self.assertGreaterEqual(len(res.tables), 2)
        self.assertIsNotNone(res.plotly_figure)
        self.assertIsNotNone(res.statistics["apparent_error_rate"])
        self.assertEqual(res.action_type, "worksheet_append_columns")

    def test_discriminant_analysis_qda(self):
        plugin = DiscriminantAnalysisPlugin()
        params = DiscriminantParams(
            group_variable="Shift",
            predictors=["Yield", "Temperature"],
            discriminant_function="Quadratic (QDA)"
        )
        res = plugin.execute(self.df, params)
        self.assertIn("Quadratic", res.statistics["function"])

    def test_correspondence_analysis_simple(self):
        plugin = CorrespondenceAnalysisPlugin()
        params = CorrespondenceParams(
            analysis_type="Simple Correspondence Analysis",
            variables=["Operator", "Shift"]
        )
        res = plugin.execute(self.df, params)
        self.assertIn("Simple Correspondence Analysis", res.title)
        self.assertEqual(len(res.tables), 2)
        self.assertIsNotNone(res.plotly_figure)
        self.assertIn("total_inertia", res.statistics)

    def test_correspondence_analysis_multiple(self):
        plugin = CorrespondenceAnalysisPlugin()
        params = CorrespondenceParams(
            analysis_type="Multiple (MCA)",
            variables=["Operator", "Shift", "Item1"]
        )
        res = plugin.execute(self.df, params)
        self.assertIn("Multiple Correspondence Analysis", res.title)
        self.assertGreater(res.statistics["total_inertia"], 0)


if __name__ == "__main__":
    unittest.main()
