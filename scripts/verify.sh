#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d /tmp/room-card-verify.XXXXXX)"
CACHE="$(mktemp -d /tmp/room-card-pycache.XXXXXX)"
cleanup() { rm -rf -- "$WORK" "$CACHE"; }
trap cleanup EXIT

if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 &&
   [[ -n "$(git -C "$ROOT" ls-files)" ]]; then
  git -C "$ROOT" archive HEAD | tar -x -C "$WORK"
else
  tar -C "$ROOT" \
    --exclude=.git --exclude=build --exclude=__pycache__ --exclude=.venv \
    -cf - . | tar -x -C "$WORK"
fi

export PYTHONPYCACHEPREFIX="$CACHE"
python3 "$WORK/scripts/secret_scan.py" --root "$WORK"
python3 "$WORK/scripts/check_repo.py" --root "$WORK"
python3 -m py_compile "$WORK"/hardware/*.py "$WORK"/scripts/*.py "$WORK"/tests/*.py
python3 -m unittest discover -s "$WORK/tests" -v

mkdir -p "$WORK/build/client-qt6"
(
  cd "$WORK/build/client-qt6"
  qmake6 ../../client/card-manager.pro
  make -j"$(nproc)"
  test -x ./card-manager
)

mkdir -p "$WORK/build/client-qt5"
(
  cd "$WORK/build/client-qt5"
  qmake ../../client/card-manager.pro
  make -j"$(nproc)"
  test -x ./card-manager
)

echo "Verification: PASS"
