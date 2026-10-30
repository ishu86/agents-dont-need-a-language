#!/bin/sh
# usage: setup_task.sh <task_id> <workdir>
# Fresh workdir = parent commit tree + the commit's test changes, no git history of the repo.
set -e
E=$(cd "$(dirname "$0")" && pwd); ID=$1; W=$2
[ -n "$ID" ] && [ -n "$W" ] || { echo "usage: $0 <id> <workdir>" >&2; exit 2; }
PARENT=$(python3 -I -c "import json,sys;print([json.loads(l) for l in open('$E/tasks.jsonl') if json.loads(l)['id']=='$ID'][0]['parent'])")
rm -rf "$W"; mkdir -p "$W"
git -C "$E/repo" archive "$PARENT" | tar -x -C "$W"
(cd "$W" && git apply "$E/tasks/$ID/test.patch" && git init -q && git add -A && git -c user.name=e17 -c user.email=e17@x commit -qm start)
echo "$W ready (python: $E/repo/.venv/bin/python, PYTHONPATH=workdir, tokenizer: pure python)"
