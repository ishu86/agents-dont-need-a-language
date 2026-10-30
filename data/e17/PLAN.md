# E17: Why do agents fail on a real large codebase? (gpt-6-luna, OpenAI SDK only)

## Question (decides whether the "agent view" tool is worth building)
On real tasks in a large repo, what share of agent failures come from **missing a non-local fact**
(a side effect, inheritance/override, global state, a coupled module the agent never read), as opposed to wrong
logic, or the environment/harness?
- Build the agent-view tool only if ≥ 30% of failures are "missed non-local fact" AND the pass rate is between 20% and 85%
  (tasks below the ceiling).
- If the pass rate is > 85%: tasks are too easy → mine harder ones (larger fixes) before concluding anything.

## Repo
sqlglot (pure Python, ~100k LOC, fast pytest). Clone to `data/e17/repo` (gitignored). Use a uv venv.

## Tasks (~24), mined from git history
A candidate is a non-merge commit that changes ≥ 1 file under `sqlglot/` (source) and ≥ 1 file under `tests/`.
Source diff 3–60 changed lines.
- Starting state = parent commit, plus the commit's test changes only (the source fix is NOT applied).
- FAIL_TO_PASS = test ids that fail at the start and pass with the full commit. Require ≥ 1.
- PASS_TO_PASS = the rest of the suite, which must pass at the start and with the full commit (exclude flaky ones).
- Prompt = commit title + body, with PR/issue numbers stripped, plus the FAIL_TO_PASS test ids. Never include the diff.
- Prefer a spread: ~1/3 with a source diff in 1 file but needing understanding of other files (dialect
  inheritance, parser↔generator coupling), ~1/3 multi-file fixes, ~1/3 small local fixes.
- Spread across the last ~2 years of history. Record source diff size, files touched, and test runtime.
Output: `data/e17/tasks.jsonl` (one object per task: id, commit, parent, title, prompt, f2p, p2p_cmd, src_files,
src_lines_changed, test_files) and per-task patches `data/e17/tasks/<id>/{test.patch,fix.patch}`.

## Agent under test
gpt-6-luna via the OpenAI Python SDK, Responses API, function tools. Reasoning effort `low` and `high` as two arms.
Tools: list_dir, read_file(path, start_line?, end_line?), grep(pattern, path?) (ripgrep or Python; output capped),
edit_file(path, old, new) (exact unique match), run_tests(args) (pytest only, inside the workdir, 300s timeout, output
capped), finish(summary). Max 60 tool steps. Log every step: tool, args, output tokens, model usage
(input/cached/output/reasoning tokens).

## Grading
After the agent finishes: run FAIL_TO_PASS (must all pass) + PASS_TO_PASS (must all pass). Record pass, regressions.

## Failure classification (after the runs)
For each failed run: a judge (gpt-6-luna, high effort) gets the task, the true fix diff, the agent's diff, and a compact
trajectory (files read, tests run). It labels: missed_nonlocal_fact | wrong_logic | incomplete (ran out of steps) |
env_or_harness | other, with a one-line reason and the non-local fact (if any). I spot-check by hand.
