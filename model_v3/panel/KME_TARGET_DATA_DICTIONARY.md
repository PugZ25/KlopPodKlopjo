# KME eight-week target data dictionary

The KME target analysis unit is `statistical_region_code × issue_week`. This is a KME-specific design selected after comparing verified municipality and statistical-region sparsity; it does not reuse the Lyme municipality horizon.

`target_kme_cases_next_8w` is the sum of canonical reported KME cases in exactly `t+1` through `t+8`. The issue week `t` is excluded. Cases are first summed from municipalities to their verified SURS 2022 statistical region using municipality code.

| Column | Meaning |
|---|---|
| `statistical_region_code` | Two-digit SURS statistical-region code. |
| `issue_week` | Canonical ISO Monday at forecast issue time. |
| `target_window_start` | Monday at `t+1`. |
| `target_window_end` | Monday at `t+8`. |
| `target_kme_cases_next_8w` | Sum of reported KME cases over `t+1..t+8`; blank when the future window is incomplete. |
| `target_status` | `complete` or `incomplete_future_window`. |
| `target_training_eligible` | `true` only when all eight future weeks exist. |

Missing future weeks are never converted to zero. This target dataset does not contain features or predictions.
