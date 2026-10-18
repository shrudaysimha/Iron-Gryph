MEMBER 3 — HOSPITAL SURGE PREDICTION DATA PACK
================================================

Files
-----
1. hourly_arrivals_cleaned.csv
   Cleaned hourly time series reconstructed from the Excel pivot table you uploaded.

2. train_surge_model_from_csv.py
   Starter machine-learning script. It creates time-based and lag features, trains a
   Random Forest regressor, evaluates it on a later holdout period, compares it with
   a simple baseline, and produces a two-hour demonstration forecast.

How to run on Windows
---------------------
1. Extract the ZIP file into one folder.
2. Open that folder in VS Code.
3. Open Terminal > New Terminal.
4. Install the Python libraries:

   python -m pip install pandas scikit-learn

5. Run:

   python train_surge_model_from_csv.py

Keep the CSV and Python script in the same folder.

What the model predicts
-----------------------
For each hour t, the target is the combined number of arrivals in hours t+1 and t+2.
The input features include the current arrival count, recent lagged counts, the hour,
the day of the week, and the month.

Data processing and caveats
---------------------------
- The supplied workbook was a pivot table, not a normal list of timestamps.
- The columns labelled "Total" duplicated the adjacent date column exactly; one copy
  was retained.
- The year rows (2014, 2015, 2016, 2017) contain 24 following rows, one per hour.
- For a date with a nonblank daily aggregate, a blank hourly cell was interpreted as
  zero because the 24 hourly values (blank treated as zero) summed exactly to the
  workbook's daily aggregate for every date checked.
- If a day aggregate was missing, or a month/day was absent from the pivot table,
  the hourly counts were left blank in the CSV. The model skips examples whose inputs
  or two-hour target depend on those missing values. It does not treat missing days
  as zero.
- The cleaned file contains 35,064 hourly calendar rows, of which
  31,973 are directly populated numeric hour cells,
  2,011 are zeros inferred from blank hour
  cells within a day whose aggregate exists, and
  1,080
  have missing arrivals that are kept blank.
- All daily totals that were available matched the sum of their 24 hourly values when
  blank hourly cells were treated as zero. Mismatches: 0.

Important source-range discrepancy
----------------------------------
The Dryad dataset description says the study used emergency-department data from
January 2014 to August 2017. However, the supplied workbook has numeric values in
the row labelled 2017 for September through December as well. This data pack follows
the workbook labels and preserves those values, but that discrepancy should be
verified with the source before you claim an exact historical coverage period.

Dataset source page:
https://datadryad.org/dataset/doi:10.5061/dryad.q57d4g4

Limitations
-----------
- This is historical aggregated data from a US hospital, not data from Bengaluru.
- No weather, event, nearby-accident, bed, staff, or ambulance features are included yet.
  Connect those only when your teammates supply properly timestamped data.
- LOW/MEDIUM/HIGH labels are demo-relative quantiles, not clinically approved thresholds.
- This is a hackathon research prototype, not a clinical or operational tool.

Useful next integration step
----------------------------
Once the model runs, ask Member 1 to agree on an API input/output format and return
a forecast object such as:
{
  "predicted_patients_next_2h": 25,
  "demand_level": "MEDIUM",
  "data_source": "historical_demo_dataset"
}

The numeric output above is an example format only, not a real model result.
