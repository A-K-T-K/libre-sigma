"""
Comprehensive test suite for OpenMinitab Regression module.
Tests all 9 modules:
  1. Fitted Line Plot (fitted_line_plot)
  2. General Regression (general_regression)
  3. Nonlinear Regression (nonlinear_regression)
  4. Stability Study / Shelf-Life Analysis (stability_study)
  5. Orthogonal Regression / Deming (orthogonal_regression)
  6. Partial Least Squares (partial_least_squares)
  7. Binary Fitted Line Plot (binary_fitted_line_plot)
  8. Logistic Regression (logistic_regression)
  9. Poisson Regression (poisson_regression)
"""

import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, "backend")
from app.plugins.modules.regression.fitted_line_plot import FittedLinePlotPlugin, FittedLinePlotParams
from app.plugins.modules.regression.general_regression import GeneralRegressionPlugin, GeneralRegressionParams
from app.plugins.modules.regression.nonlinear_regression import NonlinearRegressionPlugin, NonlinearRegressionParams
from app.plugins.modules.regression.stability_study import StabilityStudyPlugin, StabilityStudyParams
from app.plugins.modules.regression.orthogonal_regression import OrthogonalRegressionPlugin, OrthogonalRegressionParams
from app.plugins.modules.regression.partial_least_squares import PartialLeastSquaresPlugin, PlsParams
from app.plugins.modules.regression.binary_fitted_line_plot import BinaryFittedLinePlotPlugin, BinaryFittedLinePlotParams
from app.plugins.modules.regression.logistic_regression import LogisticRegressionPlugin, LogisticRegressionParams
from app.plugins.modules.regression.poisson_regression import PoissonRegressionPlugin, PoissonRegressionParams


class TestRegressionSuite(unittest.TestCase):

    def test_fitted_line_plot(self):
        plugin = FittedLinePlotPlugin()
        df = pd.DataFrame({
            "Speed": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0],
            "Dist": [15.2, 35.4, 62.1, 98.3, 142.0, 195.5, 258.0]
        })
        res = plugin.execute(df, FittedLinePlotParams(response_y="Dist", predictor_x="Speed", model_type="quadratic"))
        self.assertIsNotNone(res.tables)
        self.assertGreater(res.statistics["r_sq"], 0.95)
        self.assertIsNotNone(res.plotly_figure)

    def test_general_regression(self):
        plugin = GeneralRegressionPlugin()
        np.random.seed(42)
        x1 = np.linspace(1, 10, 30)
        x2 = np.random.uniform(5, 15, 30)
        cat = np.random.choice(["A", "B"], 30)
        y = 5.0 + 2.5 * x1 - 1.2 * x2 + (cat == "B") * 4.0 + np.random.normal(0, 0.5, 30)
        df = pd.DataFrame({"Y": y, "X1": x1, "X2": x2, "Group": cat})
        
        res = plugin.execute(df, GeneralRegressionParams(
            response_y="Y",
            continuous_predictors=["X1", "X2"],
            categorical_predictors=["Group"]
        ))
        self.assertIsNotNone(res.tables)
        self.assertGreater(res.statistics["r_sq"], 0.85)
        self.assertGreaterEqual(len(res.plotly_figure["data"]), 4)

    def test_nonlinear_regression(self):
        plugin = NonlinearRegressionPlugin()
        np.random.seed(42)
        x = np.linspace(0.1, 5.0, 25)
        # Michaelis-Menten: Y = (10 * X) / (2 + X)
        y = (10.0 * x) / (2.0 + x) + np.random.normal(0, 0.2, 25)
        df = pd.DataFrame({"Conc": x, "Rate": y})

        res = plugin.execute(df, NonlinearRegressionParams(
            response_y="Rate",
            predictor_x="Conc",
            model_function="michaelis_menten"
        ))
        self.assertIsNotNone(res.tables)
        self.assertGreater(res.statistics["r_sq"], 0.90)

    def test_stability_study(self):
        plugin = StabilityStudyPlugin()
        # 3 batches across 0, 3, 6, 9, 12 months with degradation
        np.random.seed(42)
        time = np.tile([0, 3, 6, 9, 12], 3)
        batches = np.repeat(["B1", "B2", "B3"], 5)
        potency = 100.0 - 0.5 * time + np.random.normal(0, 0.3, 15)
        df = pd.DataFrame({"Potency": potency, "Month": time, "Batch": batches})

        res = plugin.execute(df, StabilityStudyParams(
            response_y="Potency",
            time_column="Month",
            batch_column="Batch",
            lsl=90.0
        ))
        self.assertIsNotNone(res.tables)
        self.assertGreater(res.statistics["shelf_life"], 10.0)

    def test_orthogonal_regression(self):
        plugin = OrthogonalRegressionPlugin()
        np.random.seed(42)
        x_true = np.linspace(10, 100, 20)
        x_meas = x_true + np.random.normal(0, 1.0, 20)
        y_meas = 2.0 + 1.05 * x_true + np.random.normal(0, 1.0, 20)
        df = pd.DataFrame({"Method1": x_meas, "Method2": y_meas})

        res = plugin.execute(df, OrthogonalRegressionParams(
            response_y="Method2",
            predictor_x="Method1",
            error_variance_ratio=1.0
        ))
        self.assertIsNotNone(res.tables)
        self.assertAlmostEqual(res.statistics["slope"], 1.05, delta=0.2)

    def test_partial_least_squares(self):
        plugin = PartialLeastSquaresPlugin()
        np.random.seed(42)
        n = 30
        x1 = np.random.normal(0, 1, n)
        x2 = x1 + np.random.normal(0, 0.1, n) # Highly collinear
        x3 = np.random.normal(0, 1, n)
        y = 3.0 * x1 + 0.5 * x3 + np.random.normal(0, 0.3, n)
        df = pd.DataFrame({"Y": y, "X1": x1, "X2": x2, "X3": x3})

        res = plugin.execute(df, PlsParams(
            response_y="Y",
            predictors_x=["X1", "X2", "X3"],
            num_components=2
        ))
        self.assertIsNotNone(res.tables)
        self.assertGreater(res.statistics["r_sq_y"], 0.85)

    def test_binary_fitted_line_plot(self):
        plugin = BinaryFittedLinePlotPlugin()
        np.random.seed(42)
        temp = np.linspace(50, 100, 30)
        prob = 1.0 / (1.0 + np.exp(-(temp - 75) / 5))
        y = (np.random.uniform(0, 1, 30) < prob).astype(int)
        df = pd.DataFrame({"Temp": temp, "Pass": y})

        res = plugin.execute(df, BinaryFittedLinePlotParams(
            binary_response_y="Pass",
            predictor_x="Temp",
            link_function="logit"
        ))
        self.assertIsNotNone(res.tables)
        self.assertIsNotNone(res.statistics["odds_ratio"])

    def test_logistic_regression(self):
        plugin = LogisticRegressionPlugin()
        np.random.seed(42)
        x1 = np.linspace(1, 10, 40)
        prob = 1.0 / (1.0 + np.exp(-(x1 - 5.5)))
        y = np.where(np.random.uniform(0, 1, 40) < prob, "High", "Low")
        df = pd.DataFrame({"Outcome": y, "Dose": x1})

        res = plugin.execute(df, LogisticRegressionParams(
            response_y="Outcome",
            continuous_predictors=["Dose"],
            logistic_type="binary"
        ))
        self.assertIsNotNone(res.tables)
        self.assertEqual(res.statistics["type"], "binary")

    def test_poisson_regression(self):
        plugin = PoissonRegressionPlugin()
        np.random.seed(42)
        x = np.linspace(1, 10, 30)
        mu = np.exp(0.5 + 0.2 * x)
        y = np.random.poisson(mu)
        df = pd.DataFrame({"Defects": y, "Speed": x})

        res = plugin.execute(df, PoissonRegressionParams(
            count_response_y="Defects",
            continuous_predictors=["Speed"]
        ))
        self.assertIsNotNone(res.tables)
        self.assertGreater(res.statistics["dispersion_phi"], 0.0)


if __name__ == "__main__":
    unittest.main()
