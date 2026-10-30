# Experiment log (append-only)

Purpose: find what makes coding agents 10x cheaper/faster/more reliable, and whether a new language is the lever.
Rules: one entry per experiment. Record what was tried, the result, the insight, and any dead ends. Raw data lives in `results/`.
Run with `./run.sh exp/<file>.py` (uv + tiktoken + tree-sitter). Token counts use OpenAI o200k as a proxy; Claude's tokenizer is not public.
Model tests use `claude -p --model haiku --tools ""` with a fixed system prompt (`exp/llm.py`). `--bare` breaks auth; don't use it.
Rust toolchain lives in the scratchpad: RUSTUP_HOME/CARGO_HOME = `$SCRATCH/{rustup,cargo}`.

---

## 2026-10-30 — session 1

### E0 Toy syntax comparison (pre-lab, hand-written)
- Tried: the same 3 functions in py/ts/rs and an invented compact ML-style syntax.
- Result: py 110, ts 116, rs 124, compact 82 tokens.
- Insight: the best case for new syntax is about 25–35% fewer tokens. Biased upward, because I wrote the compact version.

### E1 Real-code syntax breakdown — `exp/e1_real_code_syntax.py` → `results/e1.json`
- Tried: real repos (browser-use py 657k tok, cmux ts 185k, gigatoken rs 272k). Measured tokens saved by removing comments, type annotations, or indentation.
- Result: type annotations 2.0% py / 4.3% ts / 3.4% rs. Whitespace 7–11%. Comments 3–29%.
- Insight: types are cheap. Dropping them to save tokens is a bad trade, since types catch errors (see E4). Syntax-level savings are small.

### E2 Where agent tokens go — `exp/e2_where_tokens_go.py` → `results/e2.json`
- Tried: mined 94 local Claude Code sessions (real `usage` fields plus content by chars, images excluded).
- Result (corrected, see E13 note): cost share is cache reads 72.5%, cache writes 16.0%, output 11.4%. Input:output ratio is 322:1. Code written via Write/Edit is 4.2% of content. Bash results 25.7%, Read results 5.7%.
- Insight: **the cost is re-reading context every turn, not writing code.** Every token that enters context is paid for again on every later turn. A language that writes code 30% shorter touches about 4% of content.
- Dead end: v1 counted base64 screenshots as Read output (82%). Fixed by excluding images (234M chars of images!).

### E3 Read strategies — `exp/e3_read_strategies.py` → `results/e3.json`
- Tried: whole file vs outline (function bodies replaced with `...`) vs a single function.
- Result: outline = 20% (py) / 31% (ts) / 37% (rs) of the full file. Median function 98–143 tokens vs mean file 2.7k–5.6k.
- Insight: reading by symbol or outline costs 3–5x less than whole files, and a single function is roughly 25–40x cheaper. This is the biggest lever found so far.

### E4 Checkers on 8 identical bugs — `exp/e4_checkers.py` → `results/e4.json`, raw outputs `results/e4_raw_*`
- Tried: tsc5, tsc7 (Go), pyright, mypy, ty, pyrefly (basic and strict), cargo check. Measured warm time, bugs caught, and raw vs compact (one line per error) tokens.
- Result: all catch 8/8 except **pyrefly's default preset, which catches 1/8**. Warm times: ty 0.09s, cargo 0.13s, pyrefly 0.2s, mypy 0.56s, pyright 0.68s, tsc5 ~0.5s and tsc7 ~0.2s net (npx overhead of ~0.9s subtracted). The compact format is 12% of raw for cargo, 24% for ty, 36% for pyright, 84% for tsc.
- Insight: Rust and ty errors carry 4–8x more tokens than the fix needs. Checker *defaults* matter more than speed at this scale.

### E5 Edit formats on real commits — `exp/e5_edit_formats.py` → `results/e5.json`
- Tried: replayed 660 real file edits (browser-use, finance-bus, gigatoken). Measured output tokens for rewrite, str_replace (grown until the old text is unique), unified diff, and hashline.
- Result: as % of a full rewrite, str_replace is 4–17%, udiff 5–20%, hashline 3–12%. Hashline costs about 60% of str_replace.
- Dead end: cmux has only 5 commits, so finance-bus was used for TS.

### E5b Read-side cost of line tags — `exp/e5b_hashline_read_overhead.py`
- Result: `cat -n` style (what Claude Code Read does) costs **+40%** tokens vs plain. Hashline tags cost +49%.
- Insight: line numbers on every read are a hidden 40% read tax, and input is what dominates cost (E2). Hashline saves output but adds input. Net it's likely negative unless tags are shown only where needed.

### E6 Bash output compression — `exp/e6_tool_output.py` → `results/e6.json`
- Tried: 4000 sampled real Bash outputs (out of 11,446). Cumulative filters: ANSI, progress bars, whitespace, dedupe-similar, head/tail cap.
- Result: lossless filters save only 1.5%. A lossy 60+40 line cap saves 19.5%. The top 5% of outputs carry 36% of tokens.
- Insight: outputs are already clean. The win is avoiding the few huge outputs (quiet flags, targeted commands), not generic compression.

### E7 Cross-language semantics — `data/semantics/` (cases.py / cases.ts / rs)
- Tried: 18 everyday snippets run in Python, TS (deno), Rust.
- Result: **13/18 behave differently** in at least one language (floor vs trunc division, negative mod, round-half-even vs half-up, emoji length 2/3/5, JS default sort is lexicographic, out-of-range index raises vs undefined vs panic, 1/0, max([]), big ints).
- Insight: "write once, convert to any language" means pinning semantics for every one of these cases. Naive transpiling silently changes behavior.

### E8a Live edit reliability (haiku) — `exp/e8a_edit_reliability.py` → `results/e8a_haiku.json`
- Tried: injected a one-token bug into 12 real browser-use files. Haiku fixed each via str_replace, hashline, or rewrite. Success = byte-exact restore.
- Result: 11/12 in every format (the same task failed in all three, so it was ambiguous). Mean output: str_replace 521, hashline 543, rewrite 3598 tokens.
- Insight: for 2026 models, the edit format doesn't change success. Rewrite costs 7x the output. This contradicts the "hashline 10x" claim for weak 2025 models.

### E8b Live repair: raw vs compact errors (haiku) — `exp/e8b_error_format_repair.py` → `results/e8b_haiku.json`
- Tried: the E4 fixtures (py with pyright, rs with cargo), 5 reps per arm. Success = checker passes and no print removed.
- Result: 5/5 in all arms. Feed tokens: py 437 → 156, rs 1024 → 118. Output was unchanged (~2.1k).
- Insight: compact errors cut the error feed by 64–88% with no loss of fix rate. Pure savings.
- Dead end: v1 required ≥8 prints, but the fixtures don't have 8, so it reported 0/5 falsely. Fixed by comparing with the source's own count.

### E8c Live navigation from outline (haiku) — `exp/e8c_outline_navigation.py` → `results/e8c_haiku.json`
- Tried: 15 real files (250–900 lines). Question = a function's docstring summary; answer = function name. Arms: full / outline + first docstring line / bare outline.
- Result: full 15/15 at 3869 tok, outline+doc 14/15 at 867 tok (22%), bare outline 13/15 at 748 tok (19%).
- Insight: **outline-first navigation costs 22% of the tokens and keeps ~93% of the accuracy.** Read the one function after that.

### E9 Fixed context per session — `exp/e9_baseline_context.py` → `results/e9.json`
- Result: a median of 45k tokens (p90 61k) is in context before any work: system prompt, tools, CLAUDE.md, hooks, skills. That's re-read on every model call, which makes it **19.5% of all input tokens**. Median 37 model calls per session, mean 140.
- Insight: trimming injected hooks/skills is the cheapest single fix. My own SessionStart hooks inject several plugins' text into every session.

### E10 Same tasks, model writes py/ts/rs — `exp/e10_lang_model_written.py` → `results/e10_{haiku,sonnet}.json`
- Tried: 8 tasks with hidden tests. The model writes each one in each language.
- Result: all 24/24 pass for both models. Code tokens vs Python: haiku TS 136% and Rust 177%; sonnet TS 107% and Rust 156%.
- Dead end: v1 TS failed 3/8 because the harness compared JSON with spaces. Harness bug, not the model.

### E11 Never-seen syntax taught by a 206-token spec — `exp/e11_novel_language.py` → `results/e11_{haiku,sonnet}.json`
- Tried: "Pyx" (Python semantics; fn/ret/ef/el, braces, && || !, T F nil), transpiled to Python and run on the E10 tests, 2 reps each.
- Result: **16/16 pass for both haiku and sonnet.** Code size vs the same model's Python: haiku 132%, sonnet 101%.
- Insight: (1) a small spec in context is enough for frontier-ish models on easy tasks, which agrees with Vera's result, so training data is not a blocker for *simple* code. (2) **A new syntax saved 0% in practice.** In an unfamiliar syntax, models fall back to plain loops instead of idioms (rle: 98 tokens in Pyx vs 42 in Python). The hand-written estimate (E0: −27%) did not survive model authorship.
- Not tested: hard, multi-file tasks in a novel syntax. The no-resource paper says they collapse there (0–1% on McEval-Hard without docs).

### E12 Batchable read-only hops — `exp/e12_batchable_calls.py` → `results/e12.json`
- Result: 28% of 12k model calls are read-only tool hops. 11.8% of calls directly follow another read-only hop and could merge into it, saving **10.7% of context tokens**.
- Dead end: v1 treated each content-block line as its own call (Claude Code logs one line per block) and got 1%. Fixed by grouping on message id.

### Cost and model routing
- Haiku vs sonnet on identical tasks: same pass rate (E10 24/24, E11 16/16). Haiku is 6–45x cheaper per call.
- Total live-model spend this session: ~$7.07 (API-equivalent figures reported by `claude -p`).

## Open questions for the next session
1. Hard multi-file tasks in a novel syntax (E11 harder). Needs a real task suite, e.g. SWE-style tasks with tests.
2. A real `agentc` prototype (outline reads + compact errors + quiet commands), A/B tested against plain Claude Code on 10 real tasks, measuring total $ and wall time.
3. Does dropping line numbers from Read (E5b: −29%) hurt edit accuracy?
4. Repeat E2/E9/E12 on other people's transcripts. All numbers here come from one user's 94 sessions.

### E13 Context size per model call — `exp/e13_context_per_call.py` → `results/e13.json`
- Result: across 12k calls, median context is 189k tokens, mean 223k, p90 415k. 47% of calls are over 200k, and those make up 72% of all input. Capping every call at 100k would cut input to 42%.
- Insight: **the 10x lever is context size per call, not language.** Long sessions drag 200k+ tokens through every hop. Fresh small contexts per sub-task (subagents, ledger/state-in-files, compaction) attack the 72%.
- Bug found and fixed: Claude Code writes one JSONL line per content block, and every line repeats `usage`. E2 and E9 v1 counted usage once per line instead of once per message. Fixed by deduping on message id; percentages barely moved, absolute totals had been about 2x high. Always dedupe on `message.id`.

### E14 Repo map size — `exp/e14_repo_map_size.py` → `results/e14.json`
- Tried: whole-repo map at 3 detail levels (file list / symbol names per file / first line of every def).
- Result: browser-use (404 files) 3.7k / 29.8k / 66.5k tokens; cmux (150) 1.4k / 4.6k / 11.3k; gigatoken (60) 0.5k / 5.6k / 17.4k.
- Insight: only the file list (plus about one line per file) fits a fixed-context budget, which matters because fixed context is re-read on every call (E9). Names and signatures have to be on demand, per folder or per file. Aider's repo map already does a ranked, token-budgeted version of this.

### Design decision — 2026-10-30
- The direction is saved in `DIRECTION.md`: `agentc` = map / map <dir> / outline / symbol / check, deterministic (tree-sitter), shipped as tools + a tiny skill first, with harness levers later.

### E15 Same-trajectory read ceiling (written outside this session; reviewed here) — `exp/e15_read_ceiling.py` → `results/e15.json`
- Tried: replaced every real source-file read with its outline or with its smallest function, across Claude (92 sessions), Codex (543), Cursor (93 stores). Kill threshold: under 10%.
- Result: outline saves Claude 1.46% / Codex 4.0% (my calc from its chars; the script printed none) / Cursor 5.0% of visible chars. Symbol saves 1.8% / 6.3% / 17.3%. Outline per read ≈ 23% of raw, matching E3. **KILL = yes.**
- Review: (1) Claude counted only the Read tool; `exp/e15b_bash_reads_check.py` adds 126 Bash cat/sed/head code reads, +0.63%, total 2.1%, so the verdict holds. (2) `savings_pct_of_input_side` is really % of visible chars, not % of the bill. (3) Raw keeps Read line numbers while the outline strips them, which inflates Claude savings (conservative for the kill). (4) The Codex `dollar_ok` identity (`input − cached − write ≈ 0`) assumes zero uncached input, which is probably wrong; that's why 334/472 sessions "fail". (5) Symbol = smallest function in the read, a generous ceiling.
- Insight: **outline/symbol reads are a strong per-read trick but a small session-level lever (2–5%).** REPORT lever #4 and DIRECTION were updated. The 8.4k → 0.9k worked example was a per-task best case, not typical sessions.

### E16 Strict vs loose codebase (DONE, see result below) — plan `data/e16/PLAN.md`
- Hypothesis: code built for local reasoning (explicit deps, visible side effects, Result errors, no hidden mutation) makes agents read fewer tokens at the same or better pass rate. This tests the "language for agents" idea using existing languages as proxies.
- Arms: loose_js (implicit human-convenience style), loose_ts (same plus types only), strict_ts (local-reasoning refactor). 10 tasks (6 bugs, 4 features) with hidden grading tests. The agent under test is `claude -p` with tools, haiku ×2 reps plus sonnet ×1.
- Kill: strict_ts reads ≥ 0.85x loose_js tokens with no pass-rate gain.
- Harness notes: `--setting-sources project` breaks auth (like `--bare`). `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` removes MCP tools and cut a trivial run from $0.25 to $0.003. Plugins still load (constant across arms).
- Build is done by Sonnet subagents at medium effort (fixture + runner); I verify.

### E16 result — `exp/e16_strict_vs_loose.py`, `exp/e16_analyze.py` → `results/e16_runs.jsonl`, `results/e16_analysis.json`
- Ran: 150 agent runs (haiku 10 tasks × 3 arms × 3 reps; sonnet × 2 reps). $7.13, 30M input tokens. Fixture: strict 8.4k tok, loose_ts 7.0k, loose_js 6.5k.
- Pass: 148/150 (ceiling). Only failures: sonnet loose_ts T07 (cancelOrder feature) 0/2. The task test failed and base passed.
- Reading (tool-result tokens), strict/loose_js paired by task with bootstrap 95% CI: haiku 1.03 [0.87–1.17], sonnet 0.99 [0.82–1.13]. **KILL criterion met for reading volume.**
- Types alone (loose_ts/loose_js tool tokens): haiku 0.92 [0.86–0.99], sonnet 0.85 [0.76–0.94]. **Types cut reading 8–15%.**
- Sonnet strict vs loose_js: turns 0.67 [0.56–0.80], total input 0.72 [0.62–0.84], cost 0.93 [0.88–0.98]. But strict vs loose_ts: input 0.99, turns 0.89 [0.77–1.00]. Most of the gain comes from types, not from the local-reasoning refactor.
- Haiku strict vs loose_ts: worse, total input 1.23 [1.03–1.43], turns 1.16.
- Agents read 0.4–1.1x of the whole codebase per task, i.e. nearly everything. At 7–8k tokens the whole codebase fits, so locality can't pay off. **The fixture is too small to test the real claim. Next: the same arms at 100k+ tokens, with harder tasks below the pass ceiling.**
- Also: the strict codebase is 29% larger yet was read at the same token volume, i.e. a smaller share of it (haiku 0.91 vs 1.13 codebases). That's weak and confounded by size.
- Harness: agents read mostly via Bash `cat` (auto-allowed read-only), so Read-call counts mislead. Use tool_result_tokens.

### Setup — OpenAI access (2026-10-30)
- Key is in `~/.config/agent-lab/openai.env` (chmod 600, outside the repo; load with `set -a; . ~/.config/agent-lab/openai.env; set +a`). Never commit it or print it.
- 134 models accessible, including `gpt-6-luna`, `gpt-6-sol`, `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6.1-terra`, and gpt-5.x. `gpt-6-luna` was verified via `/v1/responses`.

### E17 Why do agents fail on a real large repo? (IN PROGRESS) — plan `data/e17/PLAN.md`
- Reframe after E16: the open problem is correctness at scale (agents breaking things they didn't read), not token cost. The candidate tool is an "agent view": deterministic per-function effects, mutations, callers and covering tests for existing code.
- Gate: build it only if ≥ 30% of failures are "missed non-local fact" AND the pass rate is 20–85%.
- Agent under test: gpt-6-luna only, via the OpenAI SDK (our own tool loop), effort low and high. No Claude and no Codex as the agent. Implementation is done by Sonnet subagents at medium effort.
- Repo: sqlglot, with tasks mined from real fix commits (SWE-bench style).
- E17 setup done: 24 validated tasks (8 dialect-coupled / 8 multi-file / 8 local), 2024-10 to 2026-10. P2P is the full suite minus executor/optimizer/sqlglotc (pandas/duckdb wouldn't download, since PyPI was flaky). Tests run from source with PYTHONPATH=<workdir> and a shared venv.
- Ops lesson: the miner's parallel pytest runs pushed load avg to 34 with 111MB RAM free on a 16GB Mac. Keep validation serial and use pytest -n 2.
- Harness fix (mine): run_tests now sets PYTHONPATH=workdir and puts the venv on PATH.
- Pilot (3 tasks × low/high): 4/6 pass, 0 regressions, cache hits ~85% of input. The multi-file task e3ed7486 failed both (high effort hit 60 steps, 898k input tokens). That's below the ceiling, so it's a good difficulty level. Full run: 24 × 2 efforts × 2 reps = 96 runs.

### E17 result — `exp/e17_run.py`, `exp/e17_classify.py` → `results/e17_runs.jsonl`, `results/e17_failures.jsonl`, `results/e17_traj/`
- Ran: 96 runs of gpt-6-luna (24 real sqlglot fix tasks × low/high effort × 2 reps). About 20.7M input tokens (~90% cached), 0.26M output.
- Pass: **low 31/48 (65%), high 46/48 (96%)**. 0 regressions. By category, low: dialect-coupled 12/16, local 13/16, multi-file 6/16. High: 16/16, 16/16, 14/16 (both failures are e3ed7486, which hit 60 steps).
- Cost of high effort: 3.9x input tokens (343k vs 88k per run), 4x output, 1.8x wall time (102s vs 58s).
- Failure labels (judge = gpt-6-luna high, spot-checked by me against its reasons): wrong_logic 10, missed_nonlocal_fact 6, incomplete 3. **All 6 missed-nonlocal failures are at low effort** (35% of low failures), across 4 tasks: XMLELEMENT needing shared-parser changes (×2), Redshift EXCLUDE needing Select AST + generator support (×2), the BigQuery ALIAS_TOKENS override of the base parser, and the resolver handling nested subqueries. Spot-check: all 6 look legitimately non-local (inheritance overrides, parser↔generator coupling). A few "wrong_logic" ones (03c96cbb tokenizer-vs-parser, e3ed7486 high CTE path) are arguably non-local too, so the real share is ~30–40%.
- Harness artifact: 4 low runs ended `no_tool_call` (the model replied in text mid-task). Judged as incomplete ×2, wrong_logic ×1, missed_nonlocal ×1. Counting those as harness noise doesn't change the share (5/15 = 33%).
- Gate: low effort PASSES (pass 65%, nonlocal 35%). High effort is at the ceiling (96%).
- **Insight: the "missed non-local fact" problem is real (about 1/3 of failures), but higher reasoning effort already fixes it, at ~4x tokens.** The only opening for a tool is "high-effort accuracy at low-effort cost". Upper bound if the tool fixed every non-local miss: low goes 31 → 37/48 (77%). It can't touch wrong_logic.
- Small sample: 6 non-local failures from 4 tasks.
- Next decisive test (E18, pre-registered): low effort + a deterministic "agent view" tool (overrides/subclass definitions of a symbol across the class hierarchy, references, parser↔generator counterparts). It's worth building only if it closes ≥ 50% of the low→high pass gap at ≤ 50% of high's tokens.

### E18 Connections tool for low effort (DONE: KILLED)
- Pre-registered: arms = low (fresh baseline, 2 reps) vs low+view (2 reps), same 24 E17 tasks; E17 high is the reference (46/48, 343k input/run).
- Build the tool only if low+view reaches **≥ 39/48 pass** (≥ 50% of the low→high gap, measured against the E17 low baseline of 31/48; the fresh baseline is also reported) **and mean input ≤ 171k tokens** (≤ 50% of high). Otherwise kill.
- Tool (generic Python, deterministic, ast-based): definitions/overrides of a name across the class hierarchy, class hierarchy with per-class overridden members, references, and tests that reference a symbol.

### E18 result — `exp/e18_view.py`, `exp/e17_run.py --exp e18` → `results/e18_runs.jsonl`, `results/e18_traj/`
- Ran: 96 runs of gpt-6-luna, low effort, fresh baseline vs low+view (24 tasks × 2 reps).
- Pass: **low 32/48, low+view 34/48** (E17 low was 31/48; high 46/48). The bar was ≥ 39/48 → **KILL.** +2 tasks is within noise (pooled low baseline 63/96 = 66% vs 71%).
- Cost: low+view used 120k input/run vs 89k (+34%) and 23 steps vs 18, with 5.9 view calls per run. Under the 171k cap, but no accuracy to show for it.
- By category (low → low+view): dialect-coupled 13 → 14/16, local 13 → 13, multi-file 6 → 7.
- The 3 tasks with labelled non-local misses: 0f79f975 0 → 0/2, 994d3a37 0 → 0/2, a570cf8a 0 → 1/2.
- **Why it failed (trajectories):** the agent queried the right neighbourhood (Func/XmlElement/Postgres; Star/Redshift/STAR_EXCEPT), but the missing fact was about code that **doesn't exist yet**. The fix had to *add* parser/AST/generator support in shared modules. A connections tool can only show existing links; it can't say "you also need to add X to the generator". The non-local misses are missing design knowledge (where new code must go), not hidden existing coupling.
- Side effect: no_tool_call stops dropped from 5 to 1. The tools kept the low-effort agent working, but that didn't turn into passes.
- **Conclusion: "high-effort accuracy at low-effort cost via a deterministic connections map" does not hold.** The `agentc` connections direction is dead. Spend extra reasoning instead (E17: high = 96%).
- 2026-10-30: write-up drafted (essay, 5 figures plus 2 animations from real lab numbers; published separately).
