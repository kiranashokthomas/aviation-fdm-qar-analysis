# Aviation FDM & QAR Analysis Pipeline

![Python](https://img.shields.io/badge/Python-3.9%2B-blue) ![Pandas](https://img.shields.io/badge/Pandas-2.x-green) ![Status](https://img.shields.io/badge/Status-Active-brightgreen)

An end-to-end **Flight Data Monitoring (FDM)** pipeline for processing Quick Access Recorder (QAR) data. Detects calibrated airspeed exceedances, segments flight phases, scores event severity, and exports structured outputs for Power BI safety dashboards.

---

## Project Overview

FDM programmes are a cornerstone of proactive aviation safety management. Airlines and MROs use QAR data to monitor for exceedances against operational limits, identify trends, and trigger corrective maintenance or crew feedback.

This pipeline replicates core FDM logic:

- Ingest raw QAR telemetry (CSV-format flight parameters)
- Segment flights into phases: Takeoff, Climb, Cruise, Descent, Landing
- Detect parameter exceedances against defined operational thresholds
- Score each event by severity (Low / Medium / High / Critical)
- Flag hard landings and unstable approach indicators
- Export clean, structured outputs for Power BI reporting

---

## Repository Structure

```
aviation-fdm-qar-analysis/
|
|-- data/
|   |-- sample_qar_data.csv
|
|-- src/
|   |-- data_ingestion.py
|   |-- flight_phase_segmentation.py
|   |-- exceedance_detection.py
|   |-- severity_scoring.py
|   |-- report_exporter.py
|
|-- notebooks/
|   |-- fdm_analysis_walkthrough.ipynb
|
|-- outputs/
|   |-- exceedance_report.csv
|   |-- severity_summary.csv
|
|-- generate_sample_data.py
|-- main.py
|-- requirements.txt
|-- README.md
```

---

## Key Features

| Feature | Description |
|---|---|
| Flight Phase Segmentation | WoW signal + vertical speed: Takeoff, Climb, Cruise, Descent, Landing |
| Exceedance Detection | CAS, vertical speed, pitch, bank angle, sink rate threshold checks |
| Severity Scoring | Magnitude above threshold, duration, and flight phase context |
| Hard Landing Detection | Sink rate and g-load checks at touchdown |
| Unstable Approach Flags | Energy state and config checks below 1000ft AAL |
| Power BI-Ready Export | Structured CSV outputs for direct dashboard ingestion |

---

## Tech Stack

- **Python 3.9+**
- **Pandas** - data manipulation and time-series processing
- **NumPy** - numerical thresholding and array operations
- **Matplotlib / Seaborn** - flight parameter visualisation
- **OpenPyXL** - Excel report generation

---

## Quick Start

```bash
git clone https://github.com/kiranashokthomas/aviation-fdm-qar-analysis.git
cd aviation-fdm-qar-analysis
pip install -r requirements.txt
python generate_sample_data.py
python main.py
```

Outputs are written to the `outputs/` directory.

---

## Aviation Context

This project draws on:
- **ICAO Annex 6** - Flight recorder and FDM programme requirements
- **EASA Part-OPS** - Airline FDM/FOQA programme obligations
- Cranfield University MSc coursework in Data-Centric Aircraft Systems and Predictive Maintenance Technology

---

## Author

**Kiran Ashok Thomas**
MSc Aviation Digital Technology & Management - Cranfield University (Distinction, 70.9%)
Member, Royal Aeronautical Society (RAeS)
[LinkedIn](https://linkedin.com/in/kiranashokthomas)

---

## License

MIT License
