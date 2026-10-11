// Strategy oracle: the GSE v4.0 strategy's decision functions, translated from the Pine
// source by gse-website's test-pine-subset.mjs, run on cases written by the Python test.
//
//   node target_oracle.mjs <gse-website dir> <cases.json> <out.json>
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [, , websiteDir, casesPath, outPath] = process.argv;
const gse = path.join(websiteDir, 'tradingview', 'gse_4.0');
const read = name => readFileSync(path.join(gse, 'src', `${name}.pine`), 'utf8').replace(/\r\n/g, '\n');
const { translate } = await import(pathToFileURL(path.join(gse, 'test-pine-subset.mjs')).href);

const targets = read('strategy-targets');
const helpers = read('strategy-helpers');
// The file's own constants (const float TARGET_* = ...), read from the source.
let js = [...targets.matchAll(/^const (?:float|int) (\w+) = ([\d.]+)$/gm)].map(([, k, v]) => `const ${k} = ${v};`).join('\n') + '\n';
for (const name of ['f_target_price_valid', 'f_target_round', 'f_target_add', 'f_target_candidates', 'f_structure_targets'])
  js += translate(targets, name) + '\n';
for (const name of ['f_fresh_h4_direction', 'f_touch_pick']) js += translate(helpers, name) + '\n';

const isNA = v => v === undefined || v === null || Number.isNaN(v);
const array = {
  get: (a, i) => a[i], insert: (a, i, x) => { a.splice(i, 0, x); }, push: (a, x) => { a.push(x); },
  includes: (a, x) => a.includes(x),
};
const TargetEvidence = { new: (price, strength, major, source_key) => ({ price, strength, major, source_key }) };
const TargetCandidate = { new: (price, rr, distance_atr, score, major) => ({ price, rr, distance_atr, score, major }) };
const TargetPlan = { new: () => ({ stop: NaN, tp1: NaN, tp2: NaN, tp3: NaN, reason: '' }) };
const int = v => Math.trunc(v);
const fns = new Function('isNA', 'array', 'TargetEvidence', 'TargetCandidate', 'TargetPlan', 'int', 'ST_FRESH',
  `${js}\nreturn { f_target_add, f_structure_targets, f_touch_pick, f_fresh_h4_direction };`)(
  isNA, array, TargetEvidence, TargetCandidate, TargetPlan, int, 0);

const C = JSON.parse(readFileSync(casesPath, 'utf8'));
const n = v => (typeof v === 'number' && Number.isNaN(v) ? null : v);
const out = { targets: [], touch: [], direction: [] };
for (const c of C.targets) {
  const raw = [];
  for (const [price, strength, major, key] of c.adds) fns.f_target_add(raw, c.dir, c.entry, price, strength, major, key);
  const plan = fns.f_structure_targets(raw, c.dir, c.entry, c.wick, c.atr, c.tick);
  out.targets.push({ raw: raw.map(r => [r.price, r.strength, r.major, r.source_key]),
    stop: n(plan.stop), tp1: n(plan.tp1), tp2: n(plan.tp2), tp3: n(plan.tp3), reason: plan.reason });
}
for (const c of C.touch) {
  const levels = c.levels.map(([id, price, role, state, touches, in_contact]) => ({ id, price, role, state, touches, in_contact }));
  const best = fns.f_touch_pick(levels, c.h4_dir, c.close);
  out.touch.push(isNA(best) ? null : best.id);
}
for (const [prev, bull, bear] of C.direction) out.direction.push(fns.f_fresh_h4_direction(prev, bull, bear));
writeFileSync(outPath, JSON.stringify(out));
