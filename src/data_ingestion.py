"""
data_ingestion.py - QAR Data Loading and Validation

Handles loading, cleaning, and validating raw QAR telemetry data.
Expects CSV format with standard flight parameter columns.

Author: Kiran Ashok Thomas
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Expected QAR columns and their data types
REQUIRED_COLUMNS = [
    'flight_id', 'timestamp', 'altitude_ft', 'cas_kts',
    'vertical_speed_fpm', 'pitch_deg', 'bank_angle_deg',
    'sink_rate_fpm', 'wow_signal', 'heading_deg', 'groundspeed_kts'
]

OPTIONAL_COLUMNS = [
    'engine_n1_pct', 'flap_position', 'gear_position',
    'oat_celsius', 'wind_speed_kts', 'wind_direction_deg',
    'latitude', 'longitude'
]


def load_qar_data(filepath: str) -> pd.DataFrame:
    """
    Load QAR data from a CSV file.

    Args:
        filepath: Path to the QAR CSV file

    Returns:
        DataFrame with raw QAR telemetry

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If required columns are missing
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f'QAR data file not found: {filepath}')

    logger.info(f'Loading data from {filepath}')
    df = pd.read_csv(filepath, parse_dates=['timestamp'])

    # Check for required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f'Missing required QAR columns: {missing}')

    logger.info(f'Loaded {len(df):,} records, {df["flight_id"].nunique()} flights')
    return df


def validate_qar_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and clean QAR data.
    - Removes duplicate timestamps per flight
    - Handles missing values
    - Clips physically implausible values
    - Sorts by flight and timestamp

    Args:
        df: Raw QAR DataFrame

    Returns:
        Cleaned and validated DataFrame
    """
    initial_len = len(df)

    # Sort by flight and time
    df = df.sort_values(['flight_id', 'timestamp']).reset_index(drop=True)

    # Remove duplicate timestamps within same flight
    df = df.drop_duplicates(subset=['flight_id', 'timestamp'])
    dropped = initial_len - len(df)
    if dropped > 0:
        logger.warning(f'Dropped {dropped} duplicate records')

    # Fill minor gaps with forward-fill (max 5 consecutive)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(method='ffill', limit=5)

    # Physical plausibility bounds
    bounds = {
        'altitude_ft': (-2000, 60000),
        'cas_kts': (0, 500),
        'vertical_speed_fpm': (-10000, 10000),
        'pitch_deg': (-30, 30),
        'bank_angle_deg': (-90, 90),
        'sink_rate_fpm': (0, 5000),
    }

    for col, (low, high) in bounds.items():
        if col in df.columns:
            out_of_range = ((df[col] < low) | (df[col] > high)).sum()
            if out_of_range > 0:
                logger.warning(f'{col}: clipping {out_of_range} out-of-range values')
            df[col] = df[col].clip(low, high)

    logger.info(f'Validation complete. {len(df):,} records retained.')
    return df


def get_flight_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate a summary table with one row per flight.

    Returns:
        DataFrame with flight-level statistics
    """
    summary = df.groupby('flight_id').agg(
        start_time=('timestamp', 'min'),
        end_time=('timestamp', 'max'),
        max_altitude_ft=('altitude_ft', 'max'),
        max_cas_kts=('cas_kts', 'max'),
        max_bank_angle=('bank_angle_deg', lambda x: x.abs().max()),
        records=('timestamp', 'count')
    ).reset_index()

    summary['duration_min'] = (
        (summary['end_time'] - summary['start_time']).dt.total_seconds() / 60
    ).round(1)

    return summary
