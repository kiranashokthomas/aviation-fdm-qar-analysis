"""
exceedance_detection.py - FDM Exceedance Detection Engine

Detects parameter exceedances against operational thresholds.
Covers: CAS, vertical speed, pitch, bank angle, sink rate,
        hard landings, and unstable approach indicators.

Author: Kiran Ashok Thomas
"""

import pandas as pd
import numpy as np
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# =============================================================================
# OPERATIONAL THRESHOLDS
# Based on typical commercial airline FDM programme limits
# =============================================================================

THRESHOLDS = {
    'cas_exceedance': {
        'parameter': 'cas_kts',
        'phases': ['CLIMB', 'CRUISE', 'DESCENT'],
        'limit': 350,
        'description': 'Calibrated Airspeed exceedance'
    },
    'high_vertical_speed_descent': {
        'parameter': 'vertical_speed_fpm',
        'phases': ['DESCENT', 'APPROACH'],
        'limit': -2500,
        'direction': 'below',
        'description': 'Excessive descent rate'
    },
    'high_bank_angle': {
        'parameter': 'bank_angle_deg',
        'phases': ['CLIMB', 'CRUISE', 'DESCENT', 'APPROACH'],
        'limit': 35,
        'use_abs': True,
        'description': 'Excessive bank angle'
    },
    'high_pitch_up': {
        'parameter': 'pitch_deg',
        'phases': ['CLIMB', 'CRUISE'],
        'limit': 20,
        'description': 'Excessive pitch up'
    },
    'high_pitch_down': {
        'parameter': 'pitch_deg',
        'phases': ['DESCENT', 'APPROACH'],
        'limit': -10,
        'direction': 'below',
        'description': 'Excessive nose-down pitch'
    },
    'hard_landing': {
        'parameter': 'sink_rate_fpm',
        'phases': ['LANDING'],
        'limit': 600,
        'description': 'Hard landing (sink rate at touchdown)'
    },
    'unstable_approach_sink_rate': {
        'parameter': 'sink_rate_fpm',
        'phases': ['APPROACH'],
        'limit': 1200,
        'description': 'Unstable approach - excessive sink rate'
    },
}

# Minimum duration (seconds) for an exceedance to be recorded
MIN_EXCEEDANCE_DURATION_S = 2


def detect_exceedances(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect all exceedance events across all flights.

    Args:
        df: QAR DataFrame with 'flight_phase' column

    Returns:
        DataFrame of exceedance events with metadata
    """
    all_events = []

    for flight_id, flight_df in df.groupby('flight_id'):
        for exc_name, config in THRESHOLDS.items():
            events = _detect_single_exceedance(
                flight_df, flight_id, exc_name, config
            )
            all_events.extend(events)

    if not all_events:
        logger.info('No exceedances detected.')
        return pd.DataFrame()

    exceedances_df = pd.DataFrame(all_events)
    exceedances_df = exceedances_df.sort_values(['flight_id', 'event_start'])
    exceedances_df = exceedances_df.reset_index(drop=True)

    logger.info(f'{len(exceedances_df)} exceedance events detected.')
    return exceedances_df


def _detect_single_exceedance(
    flight_df: pd.DataFrame,
    flight_id: str,
    exc_name: str,
    config: Dict
) -> List[Dict]:
    """
    Detect exceedances of a single parameter type for one flight.
    Groups consecutive frames into events.
    """
    param = config['parameter']
    phases = config['phases']
    limit = config['limit']
    direction = config.get('direction', 'above')
    use_abs = config.get('use_abs', False)
    description = config['description']

    if param not in flight_df.columns:
        return []

    # Filter to relevant phases
    phase_mask = flight_df['flight_phase'].isin(phases)
    relevant = flight_df[phase_mask].copy()

    if relevant.empty:
        return []

    # Compute values
    values = relevant[param]
    if use_abs:
        values = values.abs()

    # Create exceedance mask
    if direction == 'above':
        exc_mask = values > limit
    else:
        exc_mask = values < limit

    if not exc_mask.any():
        return []

    # Group consecutive exceedance frames into events
    events = []
    relevant = relevant.copy()
    relevant['_exc'] = exc_mask.values

    in_event = False
    event_start_idx = None

    for idx, row in relevant.iterrows():
        if row['_exc'] and not in_event:
            in_event = True
            event_start_idx = idx
        elif not row['_exc'] and in_event:
            in_event = False
            event_df = relevant.loc[event_start_idx:idx - 1]
            event = _build_event(
                event_df, flight_id, exc_name, description, param, limit
            )
            if event:
                events.append(event)

    # Close any open event at end of data
    if in_event:
        event_df = relevant.loc[event_start_idx:]
        event = _build_event(
            event_df, flight_id, exc_name, description, param, limit
        )
        if event:
            events.append(event)

    return events


def _build_event(
    event_df: pd.DataFrame,
    flight_id: str,
    exc_name: str,
    description: str,
    param: str,
    limit: float
) -> Dict:
    """
    Build a structured exceedance event record.
    Returns None if event duration is below minimum threshold.
    """
    if event_df.empty:
        return None

    start_time = event_df['timestamp'].iloc[0]
    end_time = event_df['timestamp'].iloc[-1]
    duration_s = (end_time - start_time).total_seconds()

    if duration_s < MIN_EXCEEDANCE_DURATION_S:
        return None

    peak_value = event_df[param].abs().max()
    magnitude_above_limit = abs(peak_value - abs(limit))

    return {
        'flight_id': flight_id,
        'exceedance_type': exc_name,
        'description': description,
        'parameter': param,
        'threshold_limit': limit,
        'peak_value': round(peak_value, 2),
        'magnitude_above_limit': round(magnitude_above_limit, 2),
        'event_start': start_time,
        'event_end': end_time,
        'duration_s': round(duration_s, 1),
        'flight_phase': event_df['flight_phase'].iloc[0],
        'altitude_at_event': round(event_df['altitude_ft'].mean(), 0),
        'cas_at_event': round(event_df['cas_kts'].mean(), 1),
    }
