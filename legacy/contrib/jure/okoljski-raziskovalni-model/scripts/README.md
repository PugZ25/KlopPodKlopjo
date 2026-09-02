# Scripts

This directory contains the implementation scripts used by `okoljski_raziskovalni_model`.

Important note:

- several script filenames still keep the historical `environment_` prefix
- this is intentional for compatibility with previous work products
- the repository itself should still be referred to as `okoljski_raziskovalni_model`

Execution order:

1. `normalize_slovenia_local_data.py`
2. `build_master_weekly_panel.py`
3. `build_master_panel_variable_flags.py`
4. `build_environment_model_ready.py`
5. `run_environment_grouped_factor_ablation.py`
6. `build_environment_graphs.py`
7. `run_environment_validation.py`

Convenience runner:

- `run_environment_pipeline.py`
