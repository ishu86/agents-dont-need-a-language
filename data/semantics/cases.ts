const safe = (f: () => unknown) => { try { const v = f(); return v === undefined ? "undefined" : Array.isArray(v) ? `[${v.join(", ")}]` : String(v); } catch (e) { return "ERR:" + (e as Error).name; } };
const cases: [string, () => unknown][] = [
 ["int_overflow 2**31*2", () => 2 ** 31 * 2],
 ["big_int 2**64+1", () => 2 ** 64 + 1],
 ["div 7/2", () => 7 / 2],
 ["int_div -7//2", () => Math.floor(-7 / 2)],
 ["mod -7%3", () => -7 % 3],
 ["round 2.5", () => Math.round(2.5)],
 ["round 0.5", () => Math.round(0.5)],
 ["len emoji 'a👍'", () => "a👍".length],
 ["upper 'ß'", () => "ß".toUpperCase()],
 ["sort [10,9,1]", () => [10, 9, 1].sort()],
 ["index out of range", () => [1, 2][5]],
 ["0.1+0.2", () => 0.1 + 0.2],
 ["float fmt 1.0", () => String(1.0)],
 ["1/0", () => 1 / 0],
 ["max empty", () => Math.max(...[])],
 ["str*3", () => "ab".repeat(3)],
 ["'10' < '9'", () => "10" < "9"],
 ["int('08')", () => parseInt("08")],
];
for (const [n, f] of cases) console.log(`${n}\t${safe(f)}`);
