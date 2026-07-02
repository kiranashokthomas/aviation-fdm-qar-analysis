"""
flight_phase_segmentation.py - Flight Phase Segmentation

Segments QAR data into discrete flight phases using Weight-on-Wheels
(WoW) signal and vertical speed parameters.

Phases: GROUND | TAKEOFF | CLIMB | CRUISE | DESCENT | APPROACH | LANDING

Author: Kiran Ashok Thomas
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Flight phase labels
PHASE_GROUND = 'GROUND'
PHASE_TAKEOFF = 'TAKEOFF'
PHASE_CLIMB = 'CLIMB'
PHASE_CRUISE = 'CRUISE'
PHASE_DESCENT = 'DESCENT'
PHASE_APPROACH = 'APPROACH'
PHASE_LANDING = 'LANDING'

# Thresholds
CLIMB_VS_THRESHOLD_FPM = 500       # Positive VS above this = climbing
DESCENT_VS_THRESHOLD_FPM = -500    # Negative VS below this = descending
CRUISE_ALT_THRESHOLD_FT = 10000    # Above this and level = cruise
APPROACH_ALT_THRESHOLD_FT = 3000   # Below this on descent = approach
TAKEOFF_CAS_THRESHOLD_KTS = 80     # CAS above this on ground run = rotation zone


def segment_flight_phases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign a flight phase label to each record.

    Logic:
      - WoW=1 (on ground):
          * CAS < 80 kts -> GROUND
          * CAS >= 80 kts -> TAKEOFF
      - WoW=0 (airborne):
          * VS > +500 fpm -> CLIMB
          * VS < -500 fpm and alt > 3000ft -> DESCENT
          * VS < -500 fpm and alt <= 3000ft -> APPROACH
          * -500 <= VS <= +500 and alt >= 10000ft -> CRUISE
          * -500 <= VS <= +500 and alt < 10000ft -> APPROACH (level segment low)
      - WoW=1 after airborne phase -> LANDING

    Args:
        df: Validated QAR DataFrame

    Returns:
        DataFrame with 'flight_phase' column added
    """
    df = df.copy()
    df['flight_phase'] = PHASE_GROUND  # default

    # Process each flight independently
    results = []
    for flight_id, flight_df in df.groupby('flight_id'):
        flight_df = flight_df.copy().reset_index(drop=True)
        flight_df['flight_phase'] = _assign_phases(flight_df)
        results.append(flight_df)

    df = pd.concat(results, ignore_index=True)
    logger.info(f'Phase segmentation complete: {df["flight_phase"].value_counts().to_dict()}')
    return df


def _assign_phases(df: pd.DataFrame) -> pd.Series:
    """
    Internal phase assignment for a single flight.
    Uses a state machine approach to handle phase transitions.
    """
    phases = pd.Series(index=df.index, dtype=str)
    phases[:] = PHASE_GROUND

    wow = df['wow_signal'].values
    vs = df['vertical_speed_fpm'].values
    alt = df['altitude_ft'].values
    cas = df['cas_kts'].values

    # Track if we have been airborne (to detect landing vs taxi)
    been_airborne = False

    for i in range(len(df)):
        if wow[i] == 1:  # On ground
            if been_airborne:
                phases.iloc[i] = PHASE_LANDING
            elif cas[i] >= TAKEOFF_CAS_THRESHOLD_KTS:
                phases.iloc[i] = PHASE_TAKEOFF
            else:
                phases.iloc[i] = PHASE_GROUND
        else:  # Airborne (WoW = 0)
            been_airborne = True
            if vs[i] > CLIMB_VS_THRESHOLD_FPM:
                phases.iloc[i] = PHASE_CLIMB
            elif vs[i] < DESCENT_VS_THRESHOLD_FPM:
                if alt[i] <= APPROACH_ALT_THRESHOLD_FT:
                    phases.iloc[i] = PHASE_APPROACH
                else:
                    phases.iloc[i] = PHASE_DESCENT
            else:  # Level flight
                if alt[i] >= CRUISE_ALT_THRESHOLD_FT:
                    phases.iloc[i] = PHASE_CRUISE
                else:
                    phases.iloc[i] = PHASE_APPROACH

    # Smooth single-record noise using rolling majority vote
    phases = _smooth_phases(phases)
    return phases


def _smooth_phases(phases: pd.Series, window: int = 5) -> pd.Series:
    """
    Apply a simple rolling majority vote to reduce single-point phase flips.
    """
    smoothed = phases.copy()
    half_w = window // 2

    for i in range(half_w, len(phases) - half_w):
        window_vals = phases.iloc[i - half_w: i + half_w + 1]
        majority = window_vals.mode()
        if len(majority) > 0:
            smoothed.iloc[i] = majority.iloc[0]

    return smoothed


def get_phase_transitions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract phase transition events for each flight.

    Returns:
        DataFrame with columns: flight_id, from_phase, to_phase, timestamp, altitude_ft
    """
    transitions = []
    for flight_id, flight_df in df.groupby('flight_id'):
        prev_phase = None
        for _, row in flight_df.iterrows():
            if row['flight_phase'] != prev_phase:
                if prev_phase is not None:
                    transitions.append({
                        'flight_id': flight_id,
                        'from_phase': prev_phase,
                        'to_phase': row['flight_phase'],
                        'timestamp': row['timestamp'],
                        'altitude_ft': row['altitude_ft'],
                        'cas_kts': row['cas_kts']
                    })
                prev_phase = row['flight_phase']

    return pd.DataFrame(transitions)
