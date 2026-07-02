"""
severity_scoring.py - FDM Event Severity Scoring Engine

Scores each exceedance event on a 4-level severity scale:
  LOW | MEDIUM | HIGH | CRITICAL

Scoring factors:
  1. Magnitude above threshold (as % of limit)
  2. Duration of the event
  3. Flight phase context (some phases carry higher risk)

Author: Kiran Ashok Thomas
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Severity levels
SEV_LOW = 'LOW'
SEV_MEDIUM = 'MEDIUM'
SEV_HIGH = 'HIGH'
SEV_CRITICAL = 'CRITICAL'

# Numeric score boundaries
# Score is computed 0-100, then bucketed into labels
SCORE_LOW_MAX = 30
SCORE_MEDIUM_MAX = 60
SCORE_HIGH_MAX = 85
# > 85 = CRITICAL

# Phase risk multipliers
# Some flight phases are inherently higher risk
PHASE_RISK_MULTIPLIER = {
    'GROUND': 0.5,
    'TAKEOFF': 1.5,
    'CLIMB': 1.2,
    'CRUISE': 1.0,
    'DESCENT': 1.2,
    'APPROACH': 1.5,
    'LANDING': 1.5,
}

# Exceedance type base weights (some exceedance types are inherently more serious)
EXCEEDANCE_WEIGHTS = {
    'hard_landing': 1.4,
    'unstable_approach_sink_rate': 1.3,
    'high_bank_angle': 1.2,
    'high_pitch_down': 1.2,
    'cas_exceedance': 1.1,
    'high_vertical_speed_descent': 1.1,
    'high_pitch_up': 1.0,
}


def score_exceedances(exceedances_df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply severity scoring to all detected exceedances.

    Args:
        exceedances_df: DataFrame from detect_exceedances()

    Returns:
        DataFrame with 'severity_score' and 'severity' columns added
    """
    if exceedances_df.empty:
        logger.info('No exceedances to score.')
        return exceedances_df

    df = exceedances_df.copy()

    df['severity_score'] = df.apply(_compute_score, axis=1)
    df['severity'] = df['severity_score'].apply(_score_to_label)

    severity_summary = df['severity'].value_counts().to_dict()
    logger.info(f'Severity scoring complete: {severity_summary}')

    return df


def _compute_score(row: pd.Series) -> float:
    """
    Compute a 0-100 severity score for a single exceedance event.

    Score = magnitude_score * duration_score * phase_multiplier * type_weight
    """
    # 1. Magnitude component (0-50 points)
    #    Score proportional to how far above the limit the peak was
    limit = abs(row.get('threshold_limit', 1))
    magnitude = row.get('magnitude_above_limit', 0)
    if limit > 0:
        magnitude_pct = (magnitude / limit) * 100
    else:
        magnitude_pct = 0
    magnitude_score = min(50, magnitude_pct * 0.5)  # cap at 50

    # 2. Duration component (0-30 points)
    #    Score increases with duration, plateaus at 60 seconds
    duration_s = row.get('duration_s', 0)
    duration_score = min(30, (duration_s / 60) * 30)

    # 3. Base score (0-80)
    base_score = magnitude_score + duration_score

    # 4. Phase multiplier
    phase = row.get('flight_phase', 'CRUISE')
    phase_mult = PHASE_RISK_MULTIPLIER.get(phase, 1.0)

    # 5. Exceedance type weight
    exc_type = row.get('exceedance_type', '')
    type_weight = EXCEEDANCE_WEIGHTS.get(exc_type, 1.0)

    # Final score, clipped to 0-100
    final_score = base_score * phase_mult * type_weight
    return round(min(100, max(0, final_score)), 1)


def _score_to_label(score: float) -> str:
    """
    Convert numeric score to severity label.
    """
    if score <= SCORE_LOW_MAX:
        return SEV_LOW
    elif score <= SCORE_MEDIUM_MAX:
        return SEV_MEDIUM
    elif score <= SCORE_HIGH_MAX:
        return SEV_HIGH
    else:
        return SEV_CRITICAL


def get_severity_summary(exceedances_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate a summary of exceedances by type and severity.
    Useful for Power BI dashboard ingestion.

    Returns:
        Summary DataFrame grouped by exceedance_type and severity
    """
    if exceedances_df.empty:
        return pd.DataFrame()

    summary = exceedances_df.groupby(
        ['exceedance_type', 'severity']
    ).agg(
        count=('flight_id', 'count'),
        flights_affected=('flight_id', 'nunique'),
        avg_duration_s=('duration_s', 'mean'),
        max_peak_value=('peak_value', 'max'),
        avg_magnitude=('magnitude_above_limit', 'mean')
    ).round(2).reset_index()

    # Add severity ordering for BI sorting
    severity_order = {SEV_CRITICAL: 4, SEV_HIGH: 3, SEV_MEDIUM: 2, SEV_LOW: 1}
    summary['severity_rank'] = summary['severity'].map(severity_order)
    summary = summary.sort_values(['severity_rank', 'count'], ascending=[False, False])

    return summary.drop(columns='severity_rank')
