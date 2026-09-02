# Retrospective ERA5-Land operational prototype

This file records the superseded weekly public-weather prototype. It is not the
active refresh path. The project still uses verified ERA5-Land data for
retrospective weather ablations and model evaluation under its original
valid-time rules, but it does not extrapolate that archive into the present.

Fresh public weather delivery now uses seven completed days from Open-Meteo's
DWD ICON endpoint and is documented in
[OPERATIONAL_OPEN_METEO_WEATHER.md](OPERATIONAL_OPEN_METEO_WEATHER.md).

The earlier public prototype used `model_v3.features.weather_operational` to
retrieve four completed pre-issue ERA5-Land weeks from CDS. It required CDS
credentials and could inherit the several-day ERA5-Land-T availability delay.
Those constraints are why it was replaced for the app's descriptive recent
weather panel. ERA5-Land and ICON remain distinct sources; ICON values are not
inserted into the ERA5-Land training archive or either disease model.
