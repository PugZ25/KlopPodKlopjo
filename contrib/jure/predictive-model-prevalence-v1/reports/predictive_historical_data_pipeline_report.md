# Predictive Historical Data Pipeline Report

- generated at: `2026-04-14T12:52:50.775552+00:00`

## sync_reference_inputs

- exit code: `0`

```powershell
C:\Users\George\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\scripts\sync_reference_inputs.py
```

### STDOUT

```text
Predictive reference sync completed.
- kept existing: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\reference data\locked_explanatory\obcina_weekly_epidemiology_KME_Boreliosis.csv
- kept existing: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\reference data\locked_explanatory\obcina_surs_population_density_yearly_features.csv
- kept existing: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\reference data\locked_explanatory\obcina_surs_log_population_yearly_features.csv
```

### STDERR

```text
<empty>
```

## era5_transform_only

- exit code: `0`

```powershell
C:\Users\George\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\GITlookup\KlopPodKlopjo-main\scripts\data\copernicus\download_era5land_slovenia.py --transform-only --start-date 2016-03-01 --end-date 2025-12-31 --raw-dir C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\raw\copernicus\era5land_slovenia --feature-dir C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia
```

### STDOUT

```text
Planned ERA5-Land download for Slovenia: 2016-03-01 -> 2025-12-31 (118 monthly files)
[1/118] 2016-03 (2016-03-01 -> 2016-03-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2016_03.nc
[2/118] 2016-04 (2016-04-01 -> 2016-04-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2016_04.nc
[3/118] 2016-05 (2016-05-01 -> 2016-05-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2016_05.nc
[4/118] 2016-06 (2016-06-01 -> 2016-06-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2016_06.nc
[5/118] 2016-07 (2016-07-01 -> 2016-07-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2016_07.nc
[6/118] 2016-08 (2016-08-01 -> 2016-08-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2016_08.nc
[7/118] 2016-09 (2016-09-01 -> 2016-09-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2016_09.nc
[8/118] 2016-10 (2016-10-01 -> 2016-10-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2016_10.nc
[9/118] 2016-11 (2016-11-01 -> 2016-11-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2016_11.nc
[10/118] 2016-12 (2016-12-01 -> 2016-12-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2016_12.nc
[11/118] 2017-01 (2017-01-01 -> 2017-01-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_01.nc
[12/118] 2017-02 (2017-02-01 -> 2017-02-28)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_02.nc
[13/118] 2017-03 (2017-03-01 -> 2017-03-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_03.nc
[14/118] 2017-04 (2017-04-01 -> 2017-04-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_04.nc
[15/118] 2017-05 (2017-05-01 -> 2017-05-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_05.nc
[16/118] 2017-06 (2017-06-01 -> 2017-06-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_06.nc
[17/118] 2017-07 (2017-07-01 -> 2017-07-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_07.nc
[18/118] 2017-08 (2017-08-01 -> 2017-08-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_08.nc
[19/118] 2017-09 (2017-09-01 -> 2017-09-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_09.nc
[20/118] 2017-10 (2017-10-01 -> 2017-10-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_10.nc
[21/118] 2017-11 (2017-11-01 -> 2017-11-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_11.nc
[22/118] 2017-12 (2017-12-01 -> 2017-12-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2017_12.nc
[23/118] 2018-01 (2018-01-01 -> 2018-01-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_01.nc
[24/118] 2018-02 (2018-02-01 -> 2018-02-28)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_02.nc
[25/118] 2018-03 (2018-03-01 -> 2018-03-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_03.nc
[26/118] 2018-04 (2018-04-01 -> 2018-04-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_04.nc
[27/118] 2018-05 (2018-05-01 -> 2018-05-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_05.nc
[28/118] 2018-06 (2018-06-01 -> 2018-06-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_06.nc
[29/118] 2018-07 (2018-07-01 -> 2018-07-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_07.nc
[30/118] 2018-08 (2018-08-01 -> 2018-08-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_08.nc
[31/118] 2018-09 (2018-09-01 -> 2018-09-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_09.nc
[32/118] 2018-10 (2018-10-01 -> 2018-10-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_10.nc
[33/118] 2018-11 (2018-11-01 -> 2018-11-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_11.nc
[34/118] 2018-12 (2018-12-01 -> 2018-12-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2018_12.nc
[35/118] 2019-01 (2019-01-01 -> 2019-01-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_01.nc
[36/118] 2019-02 (2019-02-01 -> 2019-02-28)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_02.nc
[37/118] 2019-03 (2019-03-01 -> 2019-03-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_03.nc
[38/118] 2019-04 (2019-04-01 -> 2019-04-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_04.nc
[39/118] 2019-05 (2019-05-01 -> 2019-05-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_05.nc
[40/118] 2019-06 (2019-06-01 -> 2019-06-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_06.nc
[41/118] 2019-07 (2019-07-01 -> 2019-07-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_07.nc
[42/118] 2019-08 (2019-08-01 -> 2019-08-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_08.nc
[43/118] 2019-09 (2019-09-01 -> 2019-09-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_09.nc
[44/118] 2019-10 (2019-10-01 -> 2019-10-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_10.nc
[45/118] 2019-11 (2019-11-01 -> 2019-11-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_11.nc
[46/118] 2019-12 (2019-12-01 -> 2019-12-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2019_12.nc
[47/118] 2020-01 (2020-01-01 -> 2020-01-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_01.nc
[48/118] 2020-02 (2020-02-01 -> 2020-02-29)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_02.nc
[49/118] 2020-03 (2020-03-01 -> 2020-03-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_03.nc
[50/118] 2020-04 (2020-04-01 -> 2020-04-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_04.nc
[51/118] 2020-05 (2020-05-01 -> 2020-05-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_05.nc
[52/118] 2020-06 (2020-06-01 -> 2020-06-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_06.nc
[53/118] 2020-07 (2020-07-01 -> 2020-07-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_07.nc
[54/118] 2020-08 (2020-08-01 -> 2020-08-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_08.nc
[55/118] 2020-09 (2020-09-01 -> 2020-09-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_09.nc
[56/118] 2020-10 (2020-10-01 -> 2020-10-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_10.nc
[57/118] 2020-11 (2020-11-01 -> 2020-11-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_11.nc
[58/118] 2020-12 (2020-12-01 -> 2020-12-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2020_12.nc
[59/118] 2021-01 (2021-01-01 -> 2021-01-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_01.nc
[60/118] 2021-02 (2021-02-01 -> 2021-02-28)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_02.nc
[61/118] 2021-03 (2021-03-01 -> 2021-03-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_03.nc
[62/118] 2021-04 (2021-04-01 -> 2021-04-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_04.nc
[63/118] 2021-05 (2021-05-01 -> 2021-05-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_05.nc
[64/118] 2021-06 (2021-06-01 -> 2021-06-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_06.nc
[65/118] 2021-07 (2021-07-01 -> 2021-07-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_07.nc
[66/118] 2021-08 (2021-08-01 -> 2021-08-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_08.nc
[67/118] 2021-09 (2021-09-01 -> 2021-09-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_09.nc
[68/118] 2021-10 (2021-10-01 -> 2021-10-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_10.nc
[69/118] 2021-11 (2021-11-01 -> 2021-11-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_11.nc
[70/118] 2021-12 (2021-12-01 -> 2021-12-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2021_12.nc
[71/118] 2022-01 (2022-01-01 -> 2022-01-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_01.nc
[72/118] 2022-02 (2022-02-01 -> 2022-02-28)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_02.nc
[73/118] 2022-03 (2022-03-01 -> 2022-03-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_03.nc
[74/118] 2022-04 (2022-04-01 -> 2022-04-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_04.nc
[75/118] 2022-05 (2022-05-01 -> 2022-05-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_05.nc
[76/118] 2022-06 (2022-06-01 -> 2022-06-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_06.nc
[77/118] 2022-07 (2022-07-01 -> 2022-07-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_07.nc
[78/118] 2022-08 (2022-08-01 -> 2022-08-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_08.nc
[79/118] 2022-09 (2022-09-01 -> 2022-09-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_09.nc
[80/118] 2022-10 (2022-10-01 -> 2022-10-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_10.nc
[81/118] 2022-11 (2022-11-01 -> 2022-11-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_11.nc
[82/118] 2022-12 (2022-12-01 -> 2022-12-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2022_12.nc
[83/118] 2023-01 (2023-01-01 -> 2023-01-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_01.nc
[84/118] 2023-02 (2023-02-01 -> 2023-02-28)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_02.nc
[85/118] 2023-03 (2023-03-01 -> 2023-03-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_03.nc
[86/118] 2023-04 (2023-04-01 -> 2023-04-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_04.nc
[87/118] 2023-05 (2023-05-01 -> 2023-05-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_05.nc
[88/118] 2023-06 (2023-06-01 -> 2023-06-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_06.nc
[89/118] 2023-07 (2023-07-01 -> 2023-07-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_07.nc
[90/118] 2023-08 (2023-08-01 -> 2023-08-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_08.nc
[91/118] 2023-09 (2023-09-01 -> 2023-09-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_09.nc
[92/118] 2023-10 (2023-10-01 -> 2023-10-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_10.nc
[93/118] 2023-11 (2023-11-01 -> 2023-11-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_11.nc
[94/118] 2023-12 (2023-12-01 -> 2023-12-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2023_12.nc
[95/118] 2024-01 (2024-01-01 -> 2024-01-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_01.nc
[96/118] 2024-02 (2024-02-01 -> 2024-02-29)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_02.nc
[97/118] 2024-03 (2024-03-01 -> 2024-03-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_03.nc
[98/118] 2024-04 (2024-04-01 -> 2024-04-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_04.nc
[99/118] 2024-05 (2024-05-01 -> 2024-05-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_05.nc
[100/118] 2024-06 (2024-06-01 -> 2024-06-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_06.nc
[101/118] 2024-07 (2024-07-01 -> 2024-07-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_07.nc
[102/118] 2024-08 (2024-08-01 -> 2024-08-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_08.nc
[103/118] 2024-09 (2024-09-01 -> 2024-09-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_09.nc
[104/118] 2024-10 (2024-10-01 -> 2024-10-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_10.nc
[105/118] 2024-11 (2024-11-01 -> 2024-11-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_11.nc
[106/118] 2024-12 (2024-12-01 -> 2024-12-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2024_12.nc
[107/118] 2025-01 (2025-01-01 -> 2025-01-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_01.nc
[108/118] 2025-02 (2025-02-01 -> 2025-02-28)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_02.nc
[109/118] 2025-03 (2025-03-01 -> 2025-03-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_03.nc
[110/118] 2025-04 (2025-04-01 -> 2025-04-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_04.nc
[111/118] 2025-05 (2025-05-01 -> 2025-05-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_05.nc
[112/118] 2025-06 (2025-06-01 -> 2025-06-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_06.nc
[113/118] 2025-07 (2025-07-01 -> 2025-07-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_07.nc
[114/118] 2025-08 (2025-08-01 -> 2025-08-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_08.nc
[115/118] 2025-09 (2025-09-01 -> 2025-09-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_09.nc
[116/118] 2025-10 (2025-10-01 -> 2025-10-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_10.nc
[117/118] 2025-11 (2025-11-01 -> 2025-11-30)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_11.nc
[118/118] 2025-12 (2025-12-01 -> 2025-12-31)
  features exist, skipping transform: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly\era5land_slovenia_features_2025_12.nc
ERA5-Land Slovenia workflow completed.
```

### STDERR

```text
<empty>
```

## build_municipality_weather

- exit code: `0`

```powershell
C:\Users\George\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\GITlookup\KlopPodKlopjo-main\scripts\data\copernicus\build_obcina_weekly_features.py --source-dir C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\hourly --geojson-path C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\raw\gurs\obcine-gurs-rpe.geojson --start-date 2016-03-01 --end-date 2025-12-31 --overlay-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\obcina_grid_overlay.csv --daily-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\era5land_slovenia\obcina_daily_weather.csv --weekly-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_weekly_weather_features.csv --manifest-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_weekly_weather_features_manifest.json
```

### STDOUT

```text
Municipality weather feature pipeline completed.
- overlay rows: 1043
- daily rows: 755568
- weekly rows: 107696
- weekly output: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_weekly_weather_features.csv
```

### STDERR

```text
C:\Users\George\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\xarray\backends\plugins.py:109: RuntimeWarning: Engine 'cfgrib' loading failed:
Cannot find the ecCodes library
  external_backend_entrypoints = backends_dict_from_pkg(entrypoints_unique)
```

## build_municipality_dem

- exit code: `0`

```powershell
C:\Users\George\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\GITlookup\KlopPodKlopjo-main\scripts\data\copernicus\build_obcina_dem_features.py --dem-dir C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\raw\copernicus\copernicus_dem_slovenia --geojson-path C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\raw\gurs\obcine-gurs-rpe.geojson --tile-coverage-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\copernicus_dem_slovenia\obcina_dem_tile_coverage.csv --summary-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_dem_features.csv --manifest-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_dem_features_manifest.json
```

### STDOUT

```text
Municipality DEM feature pipeline completed.
- municipality rows: 212
- tile coverage rows: 288
- summary output: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_dem_features.csv
```

### STDERR

```text
<empty>
```

## build_municipality_clc

- exit code: `0`

```powershell
C:\Users\George\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\GITlookup\KlopPodKlopjo-main\scripts\data\copernicus\build_obcina_clc_features.py --raster-path C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\raw\copernicus\clms_land_cover_slovenia\u2018_clc2018_v2020_20u1_raster100m\DATA\U2018_CLC2018_V2020_20u1.tif --geojson-path C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\raw\gurs\obcine-gurs-rpe.geojson --sampling-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\interim\features\copernicus\clms_land_cover_slovenia\obcina_clc_sampling.csv --summary-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_clc_features.csv --manifest-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_clc_features_manifest.json
```

### STDOUT

```text
Municipality CLC feature pipeline completed.
- municipality rows: 212
- sampling rows: 212
- summary output: C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_clc_features.csv
```

### STDERR

```text
<empty>
```

## build_predictive_panels

- exit code: `0`

```powershell
C:\Users\George\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\scripts\build_predictive_panels.py --weekly-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_weekly_predictive_panel.csv --municipality-monthly-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\municipality\obcina_monthly_predictive_panel.csv --slovenia-monthly-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\slovenia\slovenia_monthly_predictive_panel.csv --slovenia-yearly-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\slovenia\slovenia_yearly_predictive_panel.csv --manifest-output C:\Users\George\RavenNode-MAIN-laptop_J\Libary MAIN JS\Python-combined model v1\Predikcijski model prevalence V1\processed\predictive_panel_manifest.json
```

### STDOUT

```text
Predictive panels built successfully.
- weekly panel rows: 107696
- municipality-month rows: 24804
- slovenia-month rows: 117
- slovenia-year rows: 10
```

### STDERR

```text
<empty>
```

