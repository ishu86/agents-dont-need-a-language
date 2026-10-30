#!/bin/sh
# usage: grade.sh <task_id> <workdir>  -> JSON {f2p_pass,p2p_pass,failed_tests}
exec python3 "$(dirname "$0")/grade.py" "$@"
