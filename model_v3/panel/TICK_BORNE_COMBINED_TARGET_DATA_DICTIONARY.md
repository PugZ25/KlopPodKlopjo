# Combined Lyme + KME eight-week target data dictionary

This target is a composite count of **reported Lyme disease cases plus reported KME/TBE cases**. The project label `tick_borne_diseases` refers only to this two-disease composite and does not represent every tick-borne disease.

| Column | Meaning |
|---|---|
| `statistical_region_code` | Verified statistical-region code. |
| `issue_week` | Monday issue date t. |
| `target_window_start` | t+1 week. |
| `target_window_end` | t+8 weeks. |
| `target_reported_lyme_cases_next_8w` | Reported Lyme cases summed over t+1..t+8. |
| `target_reported_kme_cases_next_8w` | Reported KME/TBE cases summed over t+1..t+8. |
| `target_reported_lyme_plus_kme_cases_next_8w` | Exact sum of the preceding two component targets. |
| `target_status` | `complete` or `incomplete_future_window`. |
| `target_training_eligible` | True only when all eight future weeks exist. |

Issue week is excluded. Missing future weeks and missing component values are never converted to zero. The target is a surveillance count, not personal risk and not a causal measure.
