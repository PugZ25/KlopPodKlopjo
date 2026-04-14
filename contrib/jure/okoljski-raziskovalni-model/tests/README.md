# Tests

This repository currently relies on pipeline integrity checks rather than a full automated test suite.

Current integrity strategy:

- rerun the full pipeline end to end
- confirm that grouped evaluation completes
- confirm that final holdout validation completes
- inspect the generated reports in `data/processed/model_validation/`

This is sufficient for the frozen explanatory baseline, but future GitHub hardening should add unit and smoke tests around path handling and expected output files.
