# SAFE: Sepsis Anticipation and Flagging Engine

A clinical decision support system prototype for early sepsis detection in ICU settings. 

**Authors:** Eugene Ho, Imama Zahoor

## Overview

SAFE uses ICU patient data to flag sepsis risk earlier than reactive, clinician-dependent workflows. The system combines a PostgreSQL relational database, an ML risk prediction model, and a role-based user interface with tiered alerting, transparent explanations, and structured override logging. 

## Data

- **Source:** PhysioNet/Computing in Cardiology Challenge 2019
- **Final cohort:** 3,580 ICU patients, 171,736 hourly records, 40 clinical variables
- **Balanced:** equal sepsis-positive and sepsis-negative patients
- **Preprocessing:** forward-fill within patient, median imputation, stratified patient-level sampling

## Repository Contents

### Exploratory Data Analysis (`SAFE_EDA_DSS_Q1.ipynb`)
Addresses the descriptive DSS question: what proportion of ICU patients get flagged, how do patterns vary by demographics, and which clinical variable combinations most often trigger alerts. Outputs include tier distributions, demographic breakdowns, trigger co-occurrence heatmaps, correlation matrices, and KMeans patient phenotype clusters. 

### Initial Model (`analysis/sepsis_prediction_6_12h.ipynb`)
Multivariate ML pipeline for predicting sepsis 6-12 hours ahead of onset. Includes feature engineering from hourly vitals and labs, train/validation/test splits at the patient level to prevent leakage, model training, and performance evaluation (AUROC, AUPRC, sensitivity at fixed specificity).

### Sensitivity Analysis (`analysis/risk_severity_septic_shock.ipynb`)
Tests how the model behaves under realistic operating conditions: varying alert thresholds (sensitivity/specificity tradeoffs, alert volume), missing or delayed lab values, and vitals-only prediction for degraded-mode operation when labs are unavailable.

