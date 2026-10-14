Click-throughs of the page in headless Edge, on made-up data only (no real names or documents).
Run one: `sh tools/clickthrough/run.sh <scenario module>` (for example `upload_page`); `SLOW_FILE=1` adds a file that takes a few seconds to read.
Needs the dev-only `websockets` package in the venv (`python -m pip install websockets`), like `esprima` for the translation checks.
