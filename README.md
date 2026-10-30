# agents-dont-need-a-language

Can a programming language, a codebase style, or a tool built for AI coding agents make them better?

I ran 18 experiments to find out: about 570 agent runs, two model vendors, real codebases, with a kill line written down before each big experiment. Almost every idea died. Letting the model think harder beat all of them.

The full lab notebook, dead ends included, is [LOG.md](LOG.md).

## Results

| Exp | Question | Result |
|---|---|---|
| E2 | Where do coding-agent tokens go? (94 Claude Code sessions) | 72.5% of cost is re-reading cached context. Code the agent wrote is 4.2% of session content |
| E11 | Can a model write a brand-new syntax from a 206-token spec? | Yes, 16/16 pass. But its code was 101% (Sonnet) to 132% (Haiku) the size of its own Python |
| E7 | Do Python, TypeScript and Rust agree on everyday code? | 13 of 18 snippets behave differently |
| E16 | Does a strict, local-reasoning codebase make agents read less? (150 runs) | No: 0.99 to 1.03x tokens read. Types alone cut reading 8 to 15% |
| E15 | Do outline/symbol reads save much at session level? | 2 to 5% of what agents read |
| E17 | gpt-6-luna on 24 real sqlglot bug fixes, low vs high reasoning effort (96 runs) | Low 31/48, high 46/48. A third of low-effort failures missed a fact in another file |
| E18 | Does a deterministic "connections" tool close that gap? (96 runs) | 34/48 vs 32/48 baseline. The bar was 39/48, so it was killed |

## Layout

| Path | What |
|---|---|
| `exp/` | One script per experiment (`e<N>_*.py`), plus shared helpers `tok.py` and `llm.py` |
| `results/` | Raw outputs: JSON summaries, per-run JSONL, agent trajectories (`e17_traj/`, `e18_traj/`) |
| `data/bugs/` | Identical 8-bug fixtures in Python, TypeScript and Rust (E4, E8b) |
| `data/semantics/` | The 18 cross-language snippets (E7) |
| `data/e16/` | The three-arm shop codebase, 10 tasks, hidden tests, `verify.sh` (E16) |
| `data/e17/` | 24 sqlglot tasks with patches, `setup_task.sh`, `grade.sh` (E17, E18) |
| `LOG.md` | Append-only notebook: what was tried, results, dead ends |

## Reproducing

Run any experiment with `./run.sh exp/<file>.py` (needs `uv`; it pulls tiktoken, tree-sitter and openai on the fly). Requirements differ by experiment:

- E2, E6, E9, E12, E13, E15 read your own local agent transcripts (`~/.claude/projects`, plus `~/.codex` and `~/.cursor` for E15). They print aggregates only.
- E1, E3, E5, E5b, E8a, E8c, E14 read local git repos under `~/dev/`. Edit the `REPOS` / `root` lines at the top of each script to point at your own repos.
- E8a, E8b, E8c, E10, E11 and E16 call Claude through the Claude Code CLI (`claude -p`).
- E4 fetches its type checkers with `npx` and `uvx`. E4, E8b and E10 need a Rust toolchain, which the scripts look for under `$SCRATCH/rustup` and `$SCRATCH/cargo` (`SCRATCH` defaults to `/tmp/agent-lang-lab`). E10 also needs `deno`.
- E7 has no script: run `python3 cases.py`, `deno run cases.ts` and `cargo run` inside `data/semantics/` and compare the outputs.
- E17 and E18 need an OpenAI key in `~/.config/agent-lang-lab/openai.env` (`OPENAI_API_KEY=...`) and a sqlglot clone:
  `git clone https://github.com/tobymao/sqlglot data/e17/repo`, then
  `uv venv data/e17/repo/.venv && uv pip install -p data/e17/repo/.venv pytest pytest-xdist python-dateutil pytz typing_extensions`.
  Then run `export E17_PY=$PWD/data/e17/repo/.venv/bin/python` and `uv run --with openai --with tiktoken python exp/e17_run.py --help`.

## Caveats

- Token counts use OpenAI's o200k tokenizer as a proxy; Claude's tokenizer isn't public.
- Samples are small (8 to 24 tasks per experiment). The transcript experiments use one person's sessions.
- Costs are API-equivalent figures reported by the tools.
- LOG.md mentions `REPORT.md` and `DIRECTION.md`. Those were internal working notes and aren't published; everything in them is covered by LOG.md and the essay.

## License

MIT
