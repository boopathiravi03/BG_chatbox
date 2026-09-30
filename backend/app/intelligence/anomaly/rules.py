"""
Deterministic thresholds and classification rules for BG AI Anomaly Intelligence.
All anomaly classifications are evidence-driven and explainable.
"""

# Numeric Outlier Detection via Interquartile Range (IQR)
NUMERIC_IQR_FACTOR_INFO = 1.5      # Minor statistical deviation: Q3 + 1.5*IQR or Q1 - 1.5*IQR
NUMERIC_IQR_FACTOR_WARNING = 3.0   # Extreme outlier: Q3 + 3.0*IQR or Q1 - 3.0*IQR

# Chronological / Time-Series Variance
TIME_SERIES_DROP_WARNING_PCT = 50.0   # Period-over-period decline >= 50%
TIME_SERIES_SPIKE_WARNING_PCT = 200.0 # Period-over-period surge >= 200%

# Data Quality Thresholds
NULL_RATIO_INFO_PCT = 20.0     # Column null percentage >= 20%
NULL_RATIO_WARNING_PCT = 35.0  # Column null percentage >= 35%
NULL_RATIO_CRITICAL_PCT = 80.0 # Column null percentage >= 80%

# Distribution Dominance
DISTRIBUTION_DOMINANCE_WARNING_PCT = 95.0 # Single categorical segment accounts for >= 95% of data

# Referential Integrity
ORPHAN_FK_BREACH_SEVERITY = "CRITICAL"
MISSING_PK_TRANSACTIONAL_SEVERITY = "CRITICAL"
