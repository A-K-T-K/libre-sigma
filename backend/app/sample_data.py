from typing import Any, Dict, List

SAMPLE_DATASETS: Dict[str, Dict[str, Any]] = {
    "bearing_diameters": {
        "id": "bearing_diameters",
        "name": "Bearing Diameters (Quality Control)",
        "description": "Inner diameter measurements (mm) from Machine 1 and Machine 2 in an automotive parts manufacturing facility.",
        "columns": [
            {"id": "c1", "name": "Machine1", "type": "numeric"},
            {"id": "c2", "name": "Machine2", "type": "numeric"},
            {"id": "c3", "name": "Batch", "type": "text"}
        ],
        "rows": [
            {"c1": 1.498, "c2": 1.502, "c3": "Batch-A"},
            {"c1": 1.501, "c2": 1.504, "c3": "Batch-A"},
            {"c1": 1.499, "c2": 1.501, "c3": "Batch-A"},
            {"c1": 1.503, "c2": 1.506, "c3": "Batch-A"},
            {"c1": 1.497, "c2": 1.503, "c3": "Batch-A"},
            {"c1": 1.502, "c2": 1.505, "c3": "Batch-B"},
            {"c1": 1.500, "c2": 1.502, "c3": "Batch-B"},
            {"c1": 1.496, "c2": 1.507, "c3": "Batch-B"},
            {"c1": 1.504, "c2": 1.504, "c3": "Batch-B"},
            {"c1": 1.499, "c2": 1.508, "c3": "Batch-B"},
            {"c1": 1.501, "c2": 1.503, "c3": "Batch-C"},
            {"c1": 1.498, "c2": 1.505, "c3": "Batch-C"},
            {"c1": 1.502, "c2": 1.506, "c3": "Batch-C"},
            {"c1": 1.495, "c2": 1.502, "c3": "Batch-C"},
            {"c1": 1.500, "c2": 1.504, "c3": "Batch-C"},
            {"c1": 1.503, "c2": 1.507, "c3": "Batch-D"},
            {"c1": 1.497, "c2": 1.505, "c3": "Batch-D"},
            {"c1": 1.499, "c2": 1.503, "c3": "Batch-D"},
            {"c1": 1.502, "c2": 1.506, "c3": "Batch-D"},
            {"c1": 1.501, "c2": 1.508, "c3": "Batch-D"}
        ]
    },
    "factory_yield": {
        "id": "factory_yield",
        "name": "Chemical Process Yield (ANOVA)",
        "description": "Yield percentage observed across three temperature settings (Low, Medium, High).",
        "columns": [
            {"id": "c1", "name": "Yield_Pct", "type": "numeric"},
            {"id": "c2", "name": "Temperature", "type": "text"},
            {"id": "c3", "name": "Catalyst", "type": "text"}
        ],
        "rows": [
            {"c1": 78.4, "c2": "Low", "c3": "Cat-1"},
            {"c1": 79.1, "c2": "Low", "c3": "Cat-1"},
            {"c1": 77.8, "c2": "Low", "c3": "Cat-2"},
            {"c1": 80.2, "c2": "Low", "c3": "Cat-2"},
            {"c1": 76.9, "c2": "Low", "c3": "Cat-1"},
            {"c1": 81.3, "c2": "Low", "c3": "Cat-2"},
            {"c1": 84.5, "c2": "Medium", "c3": "Cat-1"},
            {"c1": 86.2, "c2": "Medium", "c3": "Cat-1"},
            {"c1": 85.0, "c2": "Medium", "c3": "Cat-2"},
            {"c1": 87.1, "c2": "Medium", "c3": "Cat-2"},
            {"c1": 83.9, "c2": "Medium", "c3": "Cat-1"},
            {"c1": 86.8, "c2": "Medium", "c3": "Cat-2"},
            {"c1": 91.2, "c2": "High", "c3": "Cat-1"},
            {"c1": 89.8, "c2": "High", "c3": "Cat-1"},
            {"c1": 93.4, "c2": "High", "c3": "Cat-2"},
            {"c1": 92.1, "c2": "High", "c3": "Cat-2"},
            {"c1": 90.5, "c2": "High", "c3": "Cat-1"},
            {"c1": 94.0, "c2": "High", "c3": "Cat-2"}
        ]
    },
    "pulse_exercise": {
        "id": "pulse_exercise",
        "name": "Pulse Rate & Exercise Study",
        "description": "Resting pulse (Pulse1) and post-running pulse (Pulse2) with exercise and smoking indicators.",
        "columns": [
            {"id": "c1", "name": "Pulse1_Rest", "type": "numeric"},
            {"id": "c2", "name": "Pulse2_Run", "type": "numeric"},
            {"id": "c3", "name": "Ran", "type": "text"},
            {"id": "c4", "name": "Smokes", "type": "text"},
            {"id": "c5", "name": "Gender", "type": "text"}
        ],
        "rows": [
            {"c1": 64, "c2": 88, "c3": "Yes", "c4": "No", "c5": "Female"},
            {"c1": 58, "c2": 70, "c3": "No", "c4": "No", "c5": "Male"},
            {"c1": 62, "c2": 96, "c3": "Yes", "c4": "No", "c5": "Female"},
            {"c1": 66, "c2": 110, "c3": "Yes", "c4": "Yes", "c5": "Male"},
            {"c1": 72, "c2": 74, "c3": "No", "c4": "No", "c5": "Female"},
            {"c1": 70, "c2": 120, "c3": "Yes", "c4": "Yes", "c5": "Male"},
            {"c1": 68, "c2": 70, "c3": "No", "c4": "No", "c5": "Female"},
            {"c1": 84, "c2": 135, "c3": "Yes", "c4": "No", "c5": "Female"},
            {"c1": 74, "c2": 76, "c3": "No", "c4": "Yes", "c5": "Male"},
            {"c1": 76, "c2": 118, "c3": "Yes", "c4": "No", "c5": "Male"},
            {"c1": 60, "c2": 62, "c3": "No", "c4": "No", "c5": "Female"},
            {"c1": 82, "c2": 128, "c3": "Yes", "c4": "Yes", "c5": "Female"},
            {"c1": 72, "c2": 71, "c3": "No", "c4": "No", "c5": "Male"},
            {"c1": 88, "c2": 140, "c3": "Yes", "c4": "No", "c5": "Female"},
            {"c1": 66, "c2": 68, "c3": "No", "c4": "No", "c5": "Male"}
        ]
    },
    "automotive_efficiency": {
        "id": "automotive_efficiency",
        "name": "Automotive Fuel Efficiency",
        "description": "Vehicle weight, horsepower, engine displacement, and MPG metrics.",
        "columns": [
            {"id": "c1", "name": "MPG", "type": "numeric"},
            {"id": "c2", "name": "Weight_lbs", "type": "numeric"},
            {"id": "c3", "name": "Horsepower", "type": "numeric"},
            {"id": "c4", "name": "Acceleration", "type": "numeric"}
        ],
        "rows": [
            {"c1": 28.0, "c2": 2605, "c3": 90, "c4": 16.5},
            {"c1": 24.0, "c2": 2914, "c3": 110, "c4": 15.0},
            {"c1": 19.0, "c2": 3410, "c3": 130, "c4": 15.8},
            {"c1": 15.0, "c2": 4140, "c3": 165, "c4": 12.0},
            {"c1": 33.0, "c2": 2155, "c3": 65, "c4": 18.0},
            {"c1": 21.0, "c2": 3190, "c3": 105, "c4": 16.2},
            {"c1": 31.0, "c2": 2220, "c3": 75, "c4": 17.5},
            {"c1": 18.0, "c2": 3620, "c3": 140, "c4": 14.5},
            {"c1": 26.0, "c2": 2735, "c3": 95, "c4": 16.0},
            {"c1": 14.0, "c2": 4360, "c3": 180, "c4": 11.5},
            {"c1": 36.0, "c2": 1985, "c3": 58, "c4": 19.2},
            {"c1": 22.0, "c2": 3085, "c3": 100, "c4": 15.5}
        ]
    },
    "taguchi_surface_finish": {
        "id": "taguchi_surface_finish",
        "name": "Taguchi L9 Experiment (Surface Finish)",
        "description": "Standard Taguchi L9(3^4) orthogonal array experiment testing Cutting Speed, Feed Rate, and Depth of Cut on Surface Finish Ra (μm).",
        "columns": [
            {"id": "c1", "name": "StdOrder", "type": "numeric"},
            {"id": "c2", "name": "RunOrder", "type": "numeric"},
            {"id": "c3", "name": "Speed", "type": "numeric"},
            {"id": "c4", "name": "Feed", "type": "numeric"},
            {"id": "c5", "name": "Depth", "type": "numeric"},
            {"id": "c6", "name": "Surface_Finish_Ra", "type": "numeric"}
        ],
        "rows": [
            {"c1": 1, "c2": 1, "c3": 1, "c4": 1, "c5": 1, "c6": 1.25},
            {"c1": 2, "c2": 2, "c3": 1, "c4": 2, "c5": 2, "c6": 1.48},
            {"c1": 3, "c2": 3, "c3": 1, "c4": 3, "c5": 3, "c6": 1.95},
            {"c1": 4, "c2": 4, "c3": 2, "c4": 1, "c5": 2, "c6": 0.95},
            {"c1": 5, "c2": 5, "c3": 2, "c4": 2, "c5": 3, "c6": 1.30},
            {"c1": 6, "c2": 6, "c3": 2, "c4": 3, "c5": 1, "c6": 1.70},
            {"c1": 7, "c2": 7, "c3": 3, "c4": 1, "c5": 3, "c6": 0.82},
            {"c1": 8, "c2": 8, "c3": 3, "c4": 2, "c5": 1, "c6": 1.15},
            {"c1": 9, "c2": 9, "c3": 3, "c4": 3, "c5": 2, "c6": 1.55}
        ]
    },
    "airline_passengers": {
        "id": "airline_passengers",
        "name": "Monthly Airline Passengers (Time Series)",
        "description": "Monthly totals of international airline passengers (in thousands) exhibiting strong linear trend and multiplicative 12-month seasonality.",
        "columns": [
            {"id": "c1", "name": "Period", "type": "numeric"},
            {"id": "c2", "name": "Month", "type": "text"},
            {"id": "c3", "name": "Passengers", "type": "numeric"},
            {"id": "c4", "name": "Cargo_Tons", "type": "numeric"}
        ],
        "rows": [
            {"c1": 1, "c2": "Jan-49", "c3": 112, "c4": 20.4},
            {"c1": 2, "c2": "Feb-49", "c3": 118, "c4": 21.1},
            {"c1": 3, "c2": "Mar-49", "c3": 132, "c4": 23.5},
            {"c1": 4, "c2": "Apr-49", "c3": 129, "c4": 22.8},
            {"c1": 5, "c2": "May-49", "c3": 121, "c4": 21.9},
            {"c1": 6, "c2": "Jun-49", "c3": 135, "c4": 24.2},
            {"c1": 7, "c2": "Jul-49", "c3": 148, "c4": 26.5},
            {"c1": 8, "c2": "Aug-49", "c3": 148, "c4": 26.3},
            {"c1": 9, "c2": "Sep-49", "c3": 136, "c4": 24.1},
            {"c1": 10, "c2": "Oct-49", "c3": 119, "c4": 21.0},
            {"c1": 11, "c2": "Nov-49", "c3": 104, "c4": 18.9},
            {"c1": 12, "c2": "Dec-49", "c3": 118, "c4": 21.5},
            {"c1": 13, "c2": "Jan-50", "c3": 115, "c4": 21.2},
            {"c1": 14, "c2": "Feb-50", "c3": 126, "c4": 22.9},
            {"c1": 15, "c2": "Mar-50", "c3": 141, "c4": 25.1},
            {"c1": 16, "c2": "Apr-50", "c3": 135, "c4": 24.0},
            {"c1": 17, "c2": "May-50", "c3": 125, "c4": 22.3},
            {"c1": 18, "c2": "Jun-50", "c3": 149, "c4": 26.7},
            {"c1": 19, "c2": "Jul-50", "c3": 170, "c4": 30.1},
            {"c1": 20, "c2": "Aug-50", "c3": 170, "c4": 29.8},
            {"c1": 21, "c2": "Sep-50", "c3": 158, "c4": 27.6},
            {"c1": 22, "c2": "Oct-50", "c3": 133, "c4": 23.4},
            {"c1": 23, "c2": "Nov-50", "c3": 114, "c4": 20.1},
            {"c1": 24, "c2": "Dec-50", "c3": 140, "c4": 25.0},
            {"c1": 25, "c2": "Jan-51", "c3": 145, "c4": 25.8},
            {"c1": 26, "c2": "Feb-51", "c3": 150, "c4": 26.5},
            {"c1": 27, "c2": "Mar-51", "c3": 178, "c4": 31.2},
            {"c1": 28, "c2": "Apr-51", "c3": 163, "c4": 28.7},
            {"c1": 29, "c2": "May-51", "c3": 172, "c4": 30.4},
            {"c1": 30, "c2": "Jun-51", "c3": 178, "c4": 31.5},
            {"c1": 31, "c2": "Jul-51", "c3": 199, "c4": 35.1},
            {"c1": 32, "c2": "Aug-51", "c3": 199, "c4": 34.9},
            {"c1": 33, "c2": "Sep-51", "c3": 184, "c4": 32.6},
            {"c1": 34, "c2": "Oct-51", "c3": 162, "c4": 28.9},
            {"c1": 35, "c2": "Nov-51", "c3": 146, "c4": 26.0},
            {"c1": 36, "c2": "Dec-51", "c3": 166, "c4": 29.5},
            {"c1": 37, "c2": "Jan-52", "c3": 171, "c4": 30.2},
            {"c1": 38, "c2": "Feb-52", "c3": 180, "c4": 31.8},
            {"c1": 39, "c2": "Mar-52", "c3": 193, "c4": 34.0},
            {"c1": 40, "c2": "Apr-52", "c3": 181, "c4": 32.1},
            {"c1": 41, "c2": "May-52", "c3": 183, "c4": 32.5},
            {"c1": 42, "c2": "Jun-52", "c3": 218, "c4": 38.6},
            {"c1": 43, "c2": "Jul-52", "c3": 230, "c4": 40.7},
            {"c1": 44, "c2": "Aug-52", "c3": 242, "c4": 42.9},
            {"c1": 45, "c2": "Sep-52", "c3": 209, "c4": 36.8},
            {"c1": 46, "c2": "Oct-52", "c3": 191, "c4": 33.7},
            {"c1": 47, "c2": "Nov-52", "c3": 172, "c4": 30.5},
            {"c1": 48, "c2": "Dec-52", "c3": 194, "c4": 34.2}
        ]
    },
    "quarterly_sales": {
        "id": "quarterly_sales",
        "name": "Quarterly Product Sales & Ad Spend",
        "description": "Quarterly sales revenue ($K) and advertising expenditures ($K) across 20 consecutive financial quarters.",
        "columns": [
            {"id": "c1", "name": "Quarter", "type": "text"},
            {"id": "c2", "name": "Sales", "type": "numeric"},
            {"id": "c3", "name": "Ad_Spend", "type": "numeric"}
        ],
        "rows": [
            {"c1": "Q1-Y1", "c2": 120.5, "c3": 15.2},
            {"c1": "Q2-Y1", "c2": 145.2, "c3": 18.0},
            {"c1": "Q3-Y1", "c2": 160.8, "c3": 21.5},
            {"c1": "Q4-Y1", "c2": 180.4, "c3": 25.0},
            {"c1": "Q1-Y2", "c2": 135.0, "c3": 16.5},
            {"c1": "Q2-Y2", "c2": 158.4, "c3": 19.8},
            {"c1": "Q3-Y2", "c2": 175.2, "c3": 23.0},
            {"c1": "Q4-Y2", "c2": 202.1, "c3": 28.5},
            {"c1": "Q1-Y3", "c2": 148.6, "c3": 18.0},
            {"c1": "Q2-Y3", "c2": 172.9, "c3": 22.1},
            {"c1": "Q3-Y3", "c2": 194.5, "c3": 26.4},
            {"c1": "Q4-Y3", "c2": 225.8, "c3": 31.0},
            {"c1": "Q1-Y4", "c2": 162.3, "c3": 20.0},
            {"c1": "Q2-Y4", "c2": 189.7, "c3": 24.5},
            {"c1": "Q3-Y4", "c2": 210.4, "c3": 29.0},
            {"c1": "Q4-Y4", "c2": 248.6, "c3": 35.2},
            {"c1": "Q1-Y5", "c2": 178.0, "c3": 22.5},
            {"c1": "Q2-Y5", "c2": 205.1, "c3": 27.0},
            {"c1": "Q3-Y5", "c2": 232.4, "c3": 32.0},
            {"c1": "Q4-Y5", "c2": 270.9, "c3": 39.0}
        ]
    },
    "capacitor_lifetimes": {
        "id": "capacitor_lifetimes",
        "name": "Capacitor Reliability Life Test (Right Censoring)",
        "description": "High-voltage capacitor life test times (hours x 1000) with right censoring (1 = Failure, 0 = Censored).",
        "columns": [
            {"id": "c1", "name": "Lifetime", "type": "numeric"},
            {"id": "c2", "name": "Censor", "type": "numeric"},
            {"id": "c3", "name": "Unit_ID", "type": "text"}
        ],
        "rows": [
            {"c1": 3.05, "c2": 1, "c3": "U-01"},
            {"c1": 3.74, "c2": 1, "c3": "U-02"},
            {"c1": 4.19, "c2": 1, "c3": "U-03"},
            {"c1": 4.40, "c2": 0, "c3": "U-04"},
            {"c1": 4.81, "c2": 1, "c3": "U-05"},
            {"c1": 4.84, "c2": 1, "c3": "U-06"},
            {"c1": 4.91, "c2": 0, "c3": "U-07"},
            {"c1": 5.20, "c2": 1, "c3": "U-08"},
            {"c1": 5.88, "c2": 1, "c3": "U-09"},
            {"c1": 6.20, "c2": 0, "c3": "U-10"},
            {"c1": 6.64, "c2": 1, "c3": "U-11"},
            {"c1": 6.83, "c2": 1, "c3": "U-12"},
            {"c1": 6.89, "c2": 0, "c3": "U-13"},
            {"c1": 6.94, "c2": 1, "c3": "U-14"},
            {"c1": 7.11, "c2": 1, "c3": "U-15"},
            {"c1": 7.50, "c2": 0, "c3": "U-16"},
            {"c1": 7.85, "c2": 1, "c3": "U-17"},
            {"c1": 8.00, "c2": 0, "c3": "U-18"},
            {"c1": 8.25, "c2": 1, "c3": "U-19"},
            {"c1": 8.50, "c2": 0, "c3": "U-20"}
        ]
    }
}

