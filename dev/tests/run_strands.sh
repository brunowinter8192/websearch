#!/usr/bin/env bash
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-$REPO_ROOT/venv/bin/python}"
OUT_DIR="${STRAND_OUT_DIR:-/tmp/websearch_strands}"

cd "$REPO_ROOT"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

pids=()
names=()
for test_file in dev/tests/test_*.py; do
  name="$(basename "$test_file" .py)"
  "$PYTHON" -m pytest -x -q -p no:cacheprovider --basetemp="$OUT_DIR/$name.tmp" "$test_file" \
    "$@" > "$OUT_DIR/$name.log" 2>&1 &
  pids+=($!)
  names+=("$name")
done

failed=0
for i in "${!pids[@]}"; do
  wait "${pids[$i]}"
  code=$?
  if [ "$code" -ne 0 ] && [ "$code" -ne 5 ]; then
    echo "FAIL ${names[$i]} (exit $code) -> $OUT_DIR/${names[$i]}.log"
    failed=$((failed + 1))
  fi
done

echo "strands=${#pids[@]} failed=$failed"
[ "$failed" -eq 0 ]
