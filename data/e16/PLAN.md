# E16: Does code built for local reasoning make agents read less? (strict vs loose)

## Hypothesis
Agents spend most of their tokens re-reading context (LOG E2/E13). If a codebase guarantees local reasoning
(explicit dependencies, visible side effects, explicit errors, no hidden mutation), an agent should need to read
fewer files and tokens to make a correct change, at the same or better pass rate.
Kill: strict_ts reads ≥ 0.85x the tokens of loose_js with no gain in pass rate → the idea has no evidence.

## Arms (same observable behavior, same public API)
- `loose_js`: plain JavaScript ESM written in an implicit, human-convenience style:
  module-level mutable singletons (config object, in-memory db, audit log) imported and mutated across files;
  functions that look pure but have hidden side effects (e.g. computing a total also reserves inventory or writes audit);
  functions that mutate their arguments; inconsistent error signalling (return null / throw string / return -1);
  loose coercion (some prices arrive as strings, `||` defaults that swallow 0); rules registered by side effect at
  import time (e.g. `discountRules[name] = fn` in several files) and at least one prototype/object monkeypatch.
- `loose_ts`: the same code as loose_js with TypeScript annotations added (`strict: false`, `any` allowed where JS was
  dynamic). Keeps every implicit pattern. This arm isolates "types alone".
- `strict_ts`: same behavior, refactored for local reasoning: no module-level mutable state; dependencies passed
  explicitly in a `Ctx` object ({ db, config, clock, log }); a function that writes takes what it writes to; pure
  functions are pure; explicit `Result<T, E>` error types; money is integer cents everywhere; the discount-rule registry
  is an explicit value passed in; no monkeypatching; `strict: true`.

## Domain: "shopcore" order pipeline
About 12–16 source files, 900–1400 LOC per arm. Modules: config, money, catalog, inventory, customers (VIP tiers),
pricing (discount rules, coupons), tax (by region), shipping (weight + free-shipping rules), orders (create/checkout),
refunds, notifications (email outbox), audit log, storage (in-memory db), index (public API).
Public API (identical in all arms): `src/index.{ts,js}` exports `createShop(options?)`, which returns an object with
methods (addProduct, addStock, addCustomer, createOrder, addItem, applyCoupon, checkout, refund, getOrder, outbox, audit,
...). Loose arms reset their globals inside `createShop`, so tests are independent.

## Layout (paths relative to this folder)
```
arms/<arm>/src/...            source; entry src/index.ts or src/index.js
arms/<arm>/tests/visible.test.ts   ~6 basic tests the agent CAN see and run with `deno test`
arms/<arm>/deno.json          (loose_ts: compilerOptions.strict=false; strict_ts: strict=true)
hidden/base.test.ts           full behavior suite (≥ 40 assertions) — must pass on every clean arm
tasks/Txx/task.md             prompt shown to the agent; IDENTICAL across arms; describes a symptom or feature like a
                              user report, never names files or functions
tasks/Txx/hidden.test.ts      grading test; fails on the starting state, passes after a correct fix
tasks/Txx/<arm>.bug.patch     (bug tasks only) unified diff, applied with `patch -p1` from arms/<arm>/
tasks/Txx/<arm>.fix.patch     reference fix applied after the bug patch (bug tasks) or to clean (feature tasks)
verify.sh                     checks every invariant below for every arm; prints PASS/FAIL table
```
Hidden tests import the entry through the literal placeholder `__ENTRY__`, e.g. `import { createShop } from "__ENTRY__";`.
The harness replaces it with `../src/index.ts` or `../src/index.js` after copying the test into `<workdir>/tests_hidden/`.
Run hidden tests with `deno test --no-check -A tests_hidden/`.

## Tasks (10): 6 bugs, 4 small features
Each task must need cross-module understanding, and the information needed must be NON-local in loose arms (hidden in
a global, a side effect, an import-time registration, or a mutated argument) but visible from signatures in strict_ts.
Do not make tasks solvable by reading the stack trace alone. Bugs are introduced by the bug patch, not present in clean
code. The same logical bug or feature appears in every arm.

## Invariants verify.sh must check (all arms)
1. Clean arm: `deno test` (visible) passes; hidden/base.test.ts passes.
2. For each task: starting state (clean + bug patch, or clean for features) → that task's hidden test FAILS.
3. Starting state + fix patch → that task's hidden test passes AND hidden/base passes.
4. strict_ts: `deno check src/` passes. loose_ts: `deno check src/` passes with strict=false.
