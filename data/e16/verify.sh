#!/usr/bin/env bash
# Usage: bash verify.sh [arm ...]   (default: strict_ts loose_js loose_ts; missing arm dirs are skipped)
# Invariants (PLAN.md):
#  1 clean arm: visible tests + hidden/base pass
#  2 each task's starting state (clean [+ bug patch]) FAILS its hidden test
#  3 starting state + fix patch: hidden test AND hidden/base pass
#  4 deno check src/ passes (strict_ts strict, loose_ts non-strict)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ARMS=("$@"); [ ${#ARMS[@]} -eq 0 ] && ARMS=(strict_ts loose_js loose_ts)
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
FAILS=0
ROWS=()

row() { # arm check status [note]
  ROWS+=("$(printf '%-10s %-22s %s %s' "$1" "$2" "$3" "${4:-}")")
  if [ "$3" = FAIL ]; then FAILS=$((FAILS + 1)); fi
  return 0
}

# prep ARM DIR : fresh copy of the arm
prep() { rm -rf "$2"; mkdir -p "$2"; cp -R "$HERE/arms/$1/." "$2/"; }

# hidden DIR ARM FILE : copy a hidden test in with __ENTRY__ replaced, then run it. returns deno's exit code.
run_hidden() {
  local dir="$1" arm="$2" file="$3" ext=ts
  [ "$arm" = loose_js ] && ext=js
  mkdir -p "$dir/tests_hidden"
  sed "s#__ENTRY__#../src/index.$ext#g" "$file" > "$dir/tests_hidden/$(basename "$file")"
  (cd "$dir" && deno test --no-check -A "tests_hidden/$(basename "$file")" >"$dir/out.log" 2>&1)
}

for arm in "${ARMS[@]}"; do
  [ -d "$HERE/arms/$arm" ] || { echo "skip $arm (no arms/$arm)"; continue; }
  W="$WORK/$arm"

  # 1. clean
  prep "$arm" "$W"
  (cd "$W" && deno test --no-check -A tests/ >"$W/out.log" 2>&1) && row "$arm" clean.visible PASS || row "$arm" clean.visible FAIL
  run_hidden "$W" "$arm" "$HERE/hidden/base.test.ts" && row "$arm" clean.base PASS || row "$arm" clean.base FAIL

  # 4. type check
  case "$arm" in
    loose_js) row "$arm" deno.check SKIP "(js)";;
    *) (cd "$W" && deno check src/ >"$W/out.log" 2>&1) && row "$arm" deno.check PASS || row "$arm" deno.check FAIL;;
  esac

  for T in "$HERE"/tasks/T*/; do
    t="$(basename "$T")"
    bug="$T/$arm.bug.patch"; fix="$T/$arm.fix.patch"
    if [ ! -f "$fix" ]; then row "$arm" "$t" FAIL "(missing $arm.fix.patch)"; continue; fi

    # 2. starting state fails
    prep "$arm" "$W"
    if [ -f "$bug" ]; then
      (cd "$W" && patch -p1 --quiet <"$bug" >"$W/out.log" 2>&1) || { row "$arm" "$t.start" FAIL "(bug patch does not apply)"; continue; }
    fi
    if run_hidden "$W" "$arm" "$T/hidden.test.ts"; then row "$arm" "$t.start" FAIL "(hidden test passes before fix)"; else row "$arm" "$t.start" PASS "(fails as expected)"; fi

    # 3. fix makes it pass, base still passes
    (cd "$W" && patch -p1 --quiet <"$fix" >"$W/out.log" 2>&1) || { row "$arm" "$t.fix" FAIL "(fix patch does not apply)"; continue; }
    if run_hidden "$W" "$arm" "$T/hidden.test.ts" && run_hidden "$W" "$arm" "$HERE/hidden/base.test.ts"; then
      row "$arm" "$t.fix" PASS
    else row "$arm" "$t.fix" FAIL "(hidden or base fails after fix)"; fi
    # features: the fixed tree must also type-check
    case "$arm" in loose_js) ;; *) (cd "$W" && deno check src/ >"$W/out.log" 2>&1) || row "$arm" "$t.fix.check" FAIL;; esac
  done
done

echo "ARM        CHECK                  RESULT"
printf '%s\n' "${ROWS[@]}"
echo "----"
if [ "$FAILS" -eq 0 ]; then echo "ALL PASS"; else echo "$FAILS FAIL"; exit 1; fi
