#!/bin/sh
# run.sh <scenario module>: fresh made-up data, the server on 8777, the scenario in headless Edge, the server stopped.
S="$(cd "$(dirname "$0")" && pwd)"
R="$(cd "$S/../.." && pwd)"
PY="${PY:-C:/Users/TENGA CEKAP/Documents/table-reader/.venv/Scripts/python.exe}"
HOME_DIR="$(mktemp -d)"
"$PY" "$S/serve.py" "$R" "$HOME_DIR" 8777 > "$HOME_DIR.log" 2>&1 &
PID=$!
for i in $(seq 1 60); do curl -s -o /dev/null localhost:8777/api/ping && break; sleep 0.5; done
(cd "$S" && timeout 300 "$PY" drive.py "$1")
STATUS=$?
kill $PID 2>/dev/null
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*clickthrough*serve.py*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
rm -rf "$HOME_DIR" "$HOME_DIR.log"
exit $STATUS
