import cdsapi

client = cdsapi.Client()

dataset = "reanalysis-era5-land"

request = {
    "variable": [
        "2m_temperature",
        "total_precipitation",
    ],
    "year": ["2024"],
    "month": ["07"],
    "day": ["01"],
    "time": ["00:00", "12:00"],
    "data_format": "netcdf",
    "download_format": "unarchived",
    "area": [46.9, 13.3, 45.3, 16.6]
}

target = "slovenia_test.nc"

client.retrieve(dataset, request, target)

print("Download finished:", target)