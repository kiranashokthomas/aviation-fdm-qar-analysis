"""
report_exporter.py - Report Export Module

Exports FDM analysis results to CSV and Excel formats
optimised for Power BI ingestion and stakeholder reporting.

Author: Kiran Ashok Thomas
"""

import pandas as pd
import numpy as np
import os
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def export_reports(
    exceedances_df: pd.DataFrame,
    flight_df: pd.DataFrame,
    output_dir: str
) -> dict:
    """
    Export all analysis results to the output directory.

    Generates:
      - exceedance_report.csv       : Full exceedance event log
      - severity_summary.csv        : Grouped severity counts by type
      - flight_summary.csv          : Per-flight statistics
      - phase_distribution.csv      : Phase record counts per flight
      - fdm_report_{date}.xlsx      : Combined Excel workbook

    Args:
        exceedances_df: Scored exceedances from score_exceedances()
        flight_df:      Full QAR DataFrame with phase labels
        output_dir:     Target directory for outputs

    Returns:
        Dict of output file paths
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_files = {}

    # 1. Full exceedance event log
    if not exceedances_df.empty:
        exc_path = output_path / 'exceedance_report.csv'
        _export_exceedance_report(exceedances_df, exc_path)
        output_files['exceedance_report'] = str(exc_path)

    # 2. Severity summary
    if not exceedances_df.empty and 'severity' in exceedances_df.columns:
        sev_path = output_path / 'severity_summary.csv'
        _export_severity_summary(exceedances_df, sev_path)
        output_files['severity_summary'] = str(sev_path)

    # 3. Flight summary
    flight_summary_path = output_path / 'flight_summary.csv'
    _export_flight_summary(flight_df, flight_summary_path)
    output_files['flight_summary'] = str(flight_summary_path)

    # 4. Phase distribution
    phase_path = output_path / 'phase_distribution.csv'
    _export_phase_distribution(flight_df, phase_path)
    output_files['phase_distribution'] = str(phase_path)

    # 5. Excel workbook (all sheets)
    date_str = datetime.now().strftime('%Y%m%d')
    excel_path = output_path / f'fdm_report_{date_str}.xlsx'
    _export_excel_workbook(
        exceedances_df, flight_df, excel_path
    )
    output_files['excel_workbook'] = str(excel_path)

    logger.info(f'Reports exported to {output_dir}:')
    for name, path in output_files.items():
        logger.info(f'  {name}: {path}')

    return output_files


def _export_exceedance_report(df: pd.DataFrame, filepath: Path):
    """
    Export the full exceedance event log with Power BI-friendly column names.
    """
    export_df = df.copy()

    # Rename columns for clarity in BI tools
    rename_map = {
        'flight_id': 'Flight ID',
        'exceedance_type': 'Exceedance Type',
        'description': 'Description',
        'parameter': 'Parameter',
        'threshold_limit': 'Threshold Limit',
        'peak_value': 'Peak Value',
        'magnitude_above_limit': 'Magnitude Above Limit',
        'event_start': 'Event Start',
        'event_end': 'Event End',
        'duration_s': 'Duration (s)',
        'flight_phase': 'Flight Phase',
        'altitude_at_event': 'Altitude at Event (ft)',
        'cas_at_event': 'CAS at Event (kts)',
        'severity_score': 'Severity Score',
        'severity': 'Severity'
    }
    export_df = export_df.rename(columns=rename_map)

    export_df.to_csv(filepath, index=False)
    logger.info(f'Exceedance report saved: {filepath} ({len(export_df)} events)')


def _export_severity_summary(df: pd.DataFrame, filepath: Path):
    """
    Export severity counts grouped by exceedance type and severity level.
    """
    summary = df.groupby(['exceedance_type', 'severity']).agg(
        Count=('flight_id', 'count'),
        Flights_Affected=('flight_id', 'nunique'),
        Avg_Severity_Score=('severity_score', 'mean'),
        Max_Peak_Value=('peak_value', 'max'),
        Avg_Duration_s=('duration_s', 'mean')
    ).round(2).reset_index()

    # Add total row
    totals = pd.DataFrame([{
        'exceedance_type': 'TOTAL',
        'severity': '',
        'Count': summary['Count'].sum(),
        'Flights_Affected': df['flight_id'].nunique(),
        'Avg_Severity_Score': summary['Avg_Severity_Score'].mean().round(2),
        'Max_Peak_Value': summary['Max_Peak_Value'].max(),
        'Avg_Duration_s': summary['Avg_Duration_s'].mean().round(2)
    }])
    summary = pd.concat([summary, totals], ignore_index=True)

    summary.to_csv(filepath, index=False)
    logger.info(f'Severity summary saved: {filepath}')


def _export_flight_summary(df: pd.DataFrame, filepath: Path):
    """
    Export per-flight statistics.
    """
    summary = df.groupby('flight_id').agg(
        Records=('timestamp', 'count'),
        Start_Time=('timestamp', 'min'),
        End_Time=('timestamp', 'max'),
        Max_Altitude_ft=('altitude_ft', 'max'),
        Max_CAS_kts=('cas_kts', 'max'),
        Max_VS_fpm=('vertical_speed_fpm', 'max'),
        Min_VS_fpm=('vertical_speed_fpm', 'min')
    ).reset_index()

    summary['Duration_min'] = (
        (summary['End_Time'] - summary['Start_Time']).dt.total_seconds() / 60
    ).round(1)

    summary.to_csv(filepath, index=False)
    logger.info(f'Flight summary saved: {filepath}')


def _export_phase_distribution(df: pd.DataFrame, filepath: Path):
    """
    Export phase record counts per flight.
    """
    if 'flight_phase' not in df.columns:
        return

    phase_dist = df.groupby(['flight_id', 'flight_phase']).size().reset_index()
    phase_dist.columns = ['Flight ID', 'Flight Phase', 'Record Count']
    phase_dist.to_csv(filepath, index=False)
    logger.info(f'Phase distribution saved: {filepath}')


def _export_excel_workbook(
    exceedances_df: pd.DataFrame,
    flight_df: pd.DataFrame,
    filepath: Path
):
    """
    Write all report tables to a single Excel workbook with separate sheets.
    """
    try:
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            if not exceedances_df.empty:
                exceedances_df.to_excel(
                    writer, sheet_name='Exceedance Events', index=False
                )

                if 'severity' in exceedances_df.columns:
                    sev_summary = exceedances_df.groupby(
                        ['exceedance_type', 'severity']
                    )['flight_id'].count().reset_index()
                    sev_summary.columns = ['Exceedance Type', 'Severity', 'Count']
                    sev_summary.to_excel(
                        writer, sheet_name='Severity Summary', index=False
                    )

            # Flight summary
            flight_summary = flight_df.groupby('flight_id').agg(
                Records=('timestamp', 'count'),
                Max_Altitude=('altitude_ft', 'max'),
                Max_CAS=('cas_kts', 'max')
            ).reset_index()
            flight_summary.to_excel(
                writer, sheet_name='Flight Summary', index=False
            )

            # Phase distribution
            if 'flight_phase' in flight_df.columns:
                phase_dist = flight_df.groupby(
                    ['flight_id', 'flight_phase']
                ).size().reset_index(name='Records')
                phase_dist.to_excel(
                    writer, sheet_name='Phase Distribution', index=False
                )

        logger.info(f'Excel workbook saved: {filepath}')
    except ImportError:
        logger.warning('openpyxl not available. Skipping Excel export.')
