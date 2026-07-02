"""
generate_sample_data.py - Synthetic QAR Data Generator

Generates realistic synthetic QAR flight data for testing the FDM pipeline.
Produces flights with realistic phase profiles and intentionally injects
a small number of exceedance events to validate detection logic.

Usage:
    python generate_sample_data.py
    python generate_sample_data.py --flights 10 --output data/custom_qar.csv

Author: Kiran Ashok Thomas
"""

import pandas as pd
import numpy as np
import argparse
import os
from pathlib import Path
from datetime import datetime, timedelta

# Seed for reproducibility
np.random.seed(42)

# QAR recording frequency: 1 Hz (1 record per second)
SAMPLE_RATE_HZ = 1


def generate_flight(
    flight_id: str,
    start_time: datetime,
    inject_exceedances: bool = True
) -> pd.DataFrame:
    """
    Generate a complete synthetic QAR dataset for one flight.

    Phases generated:
      GROUND (taxi) -> TAKEOFF -> CLIMB -> CRUISE -> DESCENT -> APPROACH -> LANDING -> GROUND

    Args:
        flight_id: Unique identifier for this flight
        start_time: Departure datetime
        inject_exceedances: Whether to inject exceedance events

    Returns:
        DataFrame with QAR parameters for the full flight
    """
    records = []
    t = start_time

    def add_record(phase, alt, cas, vs, pitch, bank, sink, wow, gs, heading):
        records.append({
            'flight_id': flight_id,
            'timestamp': t,
            'altitude_ft': round(alt + np.random.normal(0, 5), 1),
            'cas_kts': round(cas + np.random.normal(0, 2), 1),
            'vertical_speed_fpm': round(vs + np.random.normal(0, 50), 0),
            'pitch_deg': round(pitch + np.random.normal(0, 0.3), 2),
            'bank_angle_deg': round(bank + np.random.normal(0, 0.5), 2),
            'sink_rate_fpm': round(max(0, sink + np.random.normal(0, 20)), 1),
            'wow_signal': wow,
            'heading_deg': round((heading + np.random.normal(0, 0.5)) % 360, 1),
            'groundspeed_kts': round(cas * 1.02 + np.random.normal(0, 3), 1),
            'engine_n1_pct': round(min(100, max(20, 78 + np.random.normal(0, 2))), 1),
            'oat_celsius': round(-20 + np.random.normal(0, 1), 1)
        })

    # ----------------------------------------------------------------
    # Phase 1: Ground Taxi (120 seconds)
    # ----------------------------------------------------------------
    for _ in range(120):
        add_record('GROUND', 0, 15 + np.random.uniform(0, 10), 0, 0, 0, 0, 1, 15, 90)
        t += timedelta(seconds=1)

    # ----------------------------------------------------------------
    # Phase 2: Takeoff Roll (30 seconds, CAS 0->170)
    # ----------------------------------------------------------------
    for i in range(30):
        cas = i * (170 / 30)
        add_record('TAKEOFF', 0, cas, 0, 8, 0, 0, 1 if i < 20 else 0, cas, 90)
        t += timedelta(seconds=1)

    # ----------------------------------------------------------------
    # Phase 3: Initial Climb (600 seconds, 0 -> 15000 ft)
    # ----------------------------------------------------------------
    alt = 0
    for i in range(600):
        alt += 25  # ~1500 fpm
        cas = 200 + (i / 600) * 50
        pitch = 10 if i < 300 else 8
        add_record('CLIMB', alt, cas, 1500, pitch, np.random.uniform(-5, 5), 0, 0, cas, 90)
        t += timedelta(seconds=1)

    # ----------------------------------------------------------------
    # Phase 4: Climb to cruise (600 seconds, 15000 -> 35000 ft)
    # ----------------------------------------------------------------
    for i in range(600):
        alt += 33  # ~2000 fpm
        cas = 250 + (i / 600) * 50
        add_record('CLIMB', min(35000, alt), cas, 2000, 7, np.random.uniform(-3, 3), 0, 0, cas, 90)
        t += timedelta(seconds=1)

    # ----------------------------------------------------------------
    # Phase 5: Cruise (1800 seconds at 35000 ft)
    # ----------------------------------------------------------------
    alt = 35000
    for i in range(1800):
        cas = 300 + np.random.normal(0, 5)
        bank = np.random.normal(0, 3)
        # Inject high bank angle exceedance mid-cruise
        if inject_exceedances and 800 < i < 820:
            bank = 38 + np.random.uniform(0, 5)  # EXCEEDANCE: bank > 35 deg
        add_record('CRUISE', alt, cas, 0, 2, bank, 0, 0, cas, 90)
        t += timedelta(seconds=1)

    # ----------------------------------------------------------------
    # Phase 6: Descent (900 seconds, 35000 -> 10000 ft)
    # ----------------------------------------------------------------
    for i in range(900):
        alt -= 27  # ~1600 fpm
        cas = 280 - (i / 900) * 50
        vs = -1600
        # Inject excessive descent rate
        if inject_exceedances and 400 < i < 415:
            vs = -2800  # EXCEEDANCE: descent rate > 2500 fpm
        add_record('DESCENT', max(10000, alt), cas, vs, -2, np.random.uniform(-5, 5), abs(vs), 0, cas, 270)
        t += timedelta(seconds=1)

    # ----------------------------------------------------------------
    # Phase 7: Approach (480 seconds, 10000 -> 0 ft)
    # ----------------------------------------------------------------
    alt = 10000
    for i in range(480):
        alt -= 20
        cas = 180 - (i / 480) * 50
        sink = 700 + np.random.normal(0, 50)
        # Inject unstable approach (excessive sink rate)
        if inject_exceedances and 300 < i < 315:
            sink = 1400 + np.random.uniform(0, 200)  # EXCEEDANCE
        add_record('APPROACH', max(0, alt), cas, -1200, -3, np.random.uniform(-3, 3), sink, 0, cas, 270)
        t += timedelta(seconds=1)

    # ----------------------------------------------------------------
    # Phase 8: Landing (30 seconds)
    # ----------------------------------------------------------------
    for i in range(30):
        sink = 400 + np.random.normal(0, 50)
        # Inject hard landing on one flight
        if inject_exceedances and flight_id == 'FL003' and i < 5:
            sink = 720  # EXCEEDANCE: hard landing
        add_record('LANDING', 0, 140 - i * 4, -500, -2, 0, sink, 1, 140 - i * 4, 270)
        t += timedelta(seconds=1)

    # ----------------------------------------------------------------
    # Phase 9: Ground Rollout (60 seconds)
    # ----------------------------------------------------------------
    for i in range(60):
        add_record('GROUND', 0, max(0, 100 - i * 2), 0, 0, 0, 0, 1, max(0, 100 - i * 2), 270)
        t += timedelta(seconds=1)

    return pd.DataFrame(records)


def generate_dataset(
    n_flights: int = 6,
    output_path: str = 'data/sample_qar_data.csv'
) -> str:
    """
    Generate a multi-flight QAR dataset.

    Args:
        n_flights: Number of flights to generate
        output_path: Output CSV path

    Returns:
        Path to generated file
    """
    print(f'Generating {n_flights} synthetic QAR flights...')

    all_flights = []
    base_time = datetime(2024, 6, 1, 6, 0, 0)

    for i in range(n_flights):
        flight_id = f'FL{i + 1:03d}'
        start = base_time + timedelta(hours=i * 4)
        # Inject exceedances in first 4 flights, clean flights for 5-6
        inject = (i < 4)
        print(f'  Generating {flight_id}... (exceedances: {inject})')
        flight_df = generate_flight(flight_id, start, inject_exceedances=inject)
        all_flights.append(flight_df)

    combined = pd.concat(all_flights, ignore_index=True)

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False)

    print(f'\nDataset generated:')
    print(f'  Total records : {len(combined):,}')
    print(f'  Flights       : {combined["flight_id"].nunique()}')
    print(f'  Columns       : {list(combined.columns)}')
    print(f'  Output file   : {output_path}')
    print(f'  File size     : {os.path.getsize(output_path) / 1024:.1f} KB')

    return output_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate synthetic QAR data for FDM pipeline testing'
    )
    parser.add_argument(
        '--flights', type=int, default=6,
        help='Number of flights to generate (default: 6)'
    )
    parser.add_argument(
        '--output', type=str, default='data/sample_qar_data.csv',
        help='Output CSV path (default: data/sample_qar_data.csv)'
    )
    args = parser.parse_args()

    generate_dataset(n_flights=args.flights, output_path=args.output)
