"""
main.py - Aviation FDM & QAR Analysis Pipeline
Entry point for the full FDM analysis pipeline.

Author: Kiran Ashok Thomas
MSc Aviation Digital Technology & Management, Cranfield University
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from data_ingestion import load_qar_data, validate_qar_data
from flight_phase_segmentation import segment_flight_phases
from exceedance_detection import detect_exceedances
from severity_scoring import score_exceedances
from report_exporter import export_reports

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def run_pipeline(data_path: str = 'data/sample_qar_data.csv',
                output_dir: str = 'outputs/'):
    """
    Run the full FDM QAR analysis pipeline.

    Args:
        data_path: Path to the QAR CSV file
        output_dir: Directory to write output reports
    """
    logger.info('=' * 60)
    logger.info('Aviation FDM & QAR Analysis Pipeline')
    logger.info('=' * 60)

    # Step 1: Load and validate data
    logger.info(f'Loading QAR data from: {data_path}')
    df = load_qar_data(data_path)
    df = validate_qar_data(df)
    logger.info(f'Loaded {len(df):,} records across {df["flight_id"].nunique()} flights')

    # Step 2: Segment flight phases
    logger.info('Segmenting flight phases...')
    df = segment_flight_phases(df)
    phase_counts = df['flight_phase'].value_counts()
    logger.info(f'Flight phases segmented: {dict(phase_counts)}')

    # Step 3: Detect exceedances
    logger.info('Detecting parameter exceedances...')
    exceedances_df = detect_exceedances(df)
    logger.info(f'{len(exceedances_df)} exceedance events detected')

    if len(exceedances_df) > 0:
        for event_type, count in exceedances_df['exceedance_type'].value_counts().items():
            logger.info(f'  - {event_type}: {count} events')

    # Step 4: Score severity
    logger.info('Scoring event severity...')
    exceedances_df = score_exceedances(exceedances_df)
    severity_counts = exceedances_df['severity'].value_counts()
    logger.info(f'Severity breakdown: {dict(severity_counts)}')

    # Step 5: Export reports
    logger.info(f'Exporting reports to {output_dir}...')
    os.makedirs(output_dir, exist_ok=True)
    export_reports(exceedances_df, df, output_dir)
    logger.info('Pipeline complete.')
    logger.info('=' * 60)

    return exceedances_df


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Aviation FDM & QAR Analysis Pipeline'
    )
    parser.add_argument(
        '--data', type=str, default='data/sample_qar_data.csv',
        help='Path to QAR CSV data file'
    )
    parser.add_argument(
        '--output', type=str, default='outputs/',
        help='Output directory for reports'
    )
    args = parser.parse_args()

    run_pipeline(data_path=args.data, output_dir=args.output)
