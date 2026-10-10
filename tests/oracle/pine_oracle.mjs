// Pine oracle: runs GSE v4.0's own f_core_update and f_context_update, translated
// from the Pine source text by gse-website's test-pine-subset.mjs, candle by
// candle. Built-in series (ta.atr, ta.ema, ta.pivothigh/low, ta.sma,
// request.security, time()) are replaced by precomputed inputs, so the Python
// port and this oracle receive identical inputs and any difference is logic.
//
//   node pine_oracle.mjs <gse-website dir> <input.json> <output.jsonl>
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [, , websiteDir, inputPath, outputPath] = process.argv;
const gse = path.join(websiteDir, 'tradingview', 'gse_4.0');
const read = name => readFileSync(path.join(gse, 'src', `${name}.pine`), 'utf8').replace(/\r\n/g, '\n');
const { translate } = await import(pathToFileURL(path.join(gse, 'test-pine-subset.mjs')).href);

// Pine continuation lines (indentation not a multiple of 4) join the line above.
function joinContinuations(text) {
  const out = [];
  for (const line of text.split('\n')) {
    const indent = line.match(/^ */)[0].length;
    if (line.trim() && indent % 4 !== 0 && out.length) out[out.length - 1] += ' ' + line.trim();
    else out.push(line);
  }
  return out.join('\n');
}

// `X.new(a=b, c=d)` as the final statement becomes an object literal.
function namedResult(text, typeName) {
  return text.replace(new RegExp(`${typeName}\\.new\\((.*)\\)\\s*$`, 'm'), (_, args) =>
    '({' + args.split(',').map(a => a.trim().replace(/^(\w+)=(?!=)/, '$1: ')).join(', ') + '})');
}

const core = read('core');
const context = read('context');

// The function body of f_core_update with built-in series replaced by inputs.
let coreFn = joinContinuations(core.slice(core.indexOf('f_core_update(')));
coreFn = coreFn
  .replace('atr14 = ta.atr(14)', 'atr14 = IN.atr')
  .replace('ema20 = ta.ema(close, 20)', 'ema20 = IN.ema20')
  .replace('ema50 = ta.ema(close, 50)', 'ema50 = IN.ema50')
  .replace('ph_raw = ta.pivothigh(high, inp.swing_len, inp.swing_len)', 'ph_raw = IN.ph')
  .replace('pl_raw = ta.pivotlow(low, inp.swing_len, inp.swing_len)', 'pl_raw = IN.pl')
  .replace('a_lvl = ta.pivothigh(body_top, inp.swing_len, inp.swing_len)', 'a_lvl = IN.a_lvl')
  .replace('v_lvl = ta.pivotlow(body_bot, inp.swing_len, inp.swing_len)', 'v_lvl = IN.v_lvl')
  .replace(/, (wick|origin_bar|born_bar|kind|in_contact)=/g, ', ');
coreFn = namedResult(coreFn, 'CoreResult');
if (/\bta\./.test(coreFn)) throw new Error('unreplaced ta.* call in f_core_update');

let ctxFn = joinContinuations(context.slice(context.indexOf('f_context_update(')));
let bsKey = 0;
ctxFn = ctxFn
  .replace(/ta\.barssince\((\w+)\)/g, (_, c) => `BS(${bsKey++}, ${c})`)
  .replace('ta.sma(volume, 20)', 'IN.vol_sma20');
ctxFn = namedResult(ctxFn, 'ContextResult');
if (/\bta\./.test(ctxFn)) throw new Error('unreplaced ta.* call in f_context_update');

const helpers = [
  [core, ['f_count_role', 'f_trim_role', 'f_level_duplicate', 'f_merge_into', 'f_opened_away', 'f_pivot_history',
          'f_prune_eq_refs', 'f_resolve_bias', 'f_structure_label']],
  [context, ['f_context_pick_obstacle', 'f_context_first_obstacle', 'f_context_level_quality']],
];
let js = '';
for (const [source, names] of helpers) for (const name of names) js += translate(source, name) + '\n';
// Audit B10: the harness turns the loop's last statement into `return`; real Pine keeps looping.
js = js.replace('return array.remove(levels, oldest);', 'array.remove(levels, oldest);');
js += translate(coreFn, 'f_core_update') + '\n' + translate(ctxFn, 'f_context_update') + '\n';
writeFileSync(outputPath + '.oracle.js', js);

const D = JSON.parse(readFileSync(inputPath, 'utf8'));
const P = D.params;
const num = v => (v === null ? NaN : v);
let T = 0, IN = {}, open, high, low, close, volume, bar_index;
const isNA = v => v === undefined || v === null || Number.isNaN(v);
const nz = (v, d = 0) => (isNA(v) ? d : v);
const array = {
  get: (a, i) => a[i], remove: (a, i) => a.splice(i, 1)[0], push: (a, x) => { a.push(x); },
  shift: a => a.shift(), includes: (a, x) => a.includes(x),
};
const Lvl = { new: (id, price, role, state, touches, wick = NaN, origin_bar = NaN, born_bar = NaN, kind = '', in_contact = false) =>
  ({ id, price, role, state, touches, wick, origin_bar, born_bar, kind, in_contact }) };
const LvlEvent = { new: (kind, price) => ({ kind, price }) };
const EqPivotEvent = { new: (...a) => a };
const timeframe = { period: '15', isintraday: true, isdaily: false, change: tf => (tf === 'D' ? IN.new_day : IN.new_week) };
const time = (tf, session, tz) => ((tz === 'Asia/Tokyo' ? IN.in_asian : tz === 'Europe/London' ? IN.in_london : IN.in_ny) ? 1 : NaN);
const syminfo = { mintick: P.tick };
const barstate = { isconfirmed: true };
const color = new Proxy({}, { get: (_, k) => String(k) });
const lastTrue = new Map();
const BS = (key, cond) => { if (cond) lastTrue.set(key, bar_index); return lastTrue.has(key) ? bar_index - lastTrue.get(key) : NaN; };
const [ST_FRESH, ST_TAPPED, ST_CAND, ST_FLIP] = [0, 1, 2, 3];
const [EVT_FLIP_TO_SUP, EVT_FLIP_TO_RES, EVT_TAP_RES, EVT_TAP_SUP] = [0, 1, 4, 5];
const open_at = j => D.open[T - j], high_at = j => D.high[T - j], low_at = j => D.low[T - j], close_at = j => D.close[T - j];

const fns = new Function(
  'isNA', 'nz', 'array', 'Lvl', 'LvlEvent', 'EqPivotEvent', 'timeframe', 'time', 'syminfo', 'barstate', 'color', 'BS',
  'ST_FRESH', 'ST_TAPPED', 'ST_CAND', 'ST_FLIP', 'EVT_FLIP_TO_SUP', 'EVT_FLIP_TO_RES', 'EVT_TAP_RES', 'EVT_TAP_SUP',
  'open_at', 'high_at', 'low_at', 'close_at', 'G',
  // Series globals are read through G so the driver can set them per candle.
  `with (G) { ${js}\n return { f_core_update, f_context_update }; }`,
)(isNA, nz, array, Lvl, LvlEvent, EqPivotEvent, timeframe, time, syminfo, barstate, color, BS,
  ST_FRESH, ST_TAPPED, ST_CAND, ST_FLIP, EVT_FLIP_TO_SUP, EVT_FLIP_TO_RES, EVT_TAP_RES, EVT_TAP_SUP,
  open_at, high_at, low_at, close_at, new Proxy({}, {
    has: (_, k) => ['open', 'high', 'low', 'close', 'volume', 'bar_index', 'IN'].includes(k),
    get: (_, k) => ({ open, high, low, close, volume, bar_index, IN })[k],
  }));

const inp = { swing_len: P.swing_len, zone_count: P.zone_count, flip_on: true, flip_wick: 35.0, cluster_on: false,
  cluster_atr: 0.5, flip_max_age: 20, eq_atr: 0.15, sweep_snr_atr: 3.0, break_fallback: true };
const cinp = { space_mult: 2.0, confl_window: 15, sweep_bos_win: 6, conf_cluster: 8, rej_atr: 2.0,
  require_sweep: P.require_sweep, w_str: 35, w_loc: 30, w_conf: 25, w_time: 10, gate_cap: 60 };
const cs = { ph1: NaN, ph2: NaN, pl1: NaN, pl2: NaN, ph1_bar: NaN, pl1_bar: NaN, struct_dir: 0, used_ph_bar: NaN,
  used_pl_bar: NaN, levels: [], next_id: 0, eq_h_v: [], eq_h_b: [], eq_l_v: [], eq_l_b: [], eqh_pool: [], eql_pool: [],
  pdh_consumed: false, pdl_consumed: false, pwh_consumed: false, pwl_consumed: false,
  last_pd_h: NaN, last_pd_l: NaN, last_pw_h: NaN, last_pw_l: NaN, swing_h_consumed: false, swing_l_consumed: false };
const ds = { bull_sweep_bar1: NaN, bear_sweep_bar1: NaN, last_bull_bos_bar: NaN, last_bear_bos_bar: NaN,
  bull_bos_had_sweep: false, bear_bos_had_sweep: false };

const lines = [];
const n = D.close.length;
for (T = 0; T < n; T++) {
  bar_index = T;
  [open, high, low, close, volume] = [D.open[T], D.high[T], D.low[T], D.close[T], D.volume[T]];
  IN = {};
  for (const k of ['atr', 'ema20', 'ema50', 'ph', 'pl', 'a_lvl', 'v_lvl', 'vol_sma20', 'pd_h', 'pd_l', 'pw_h', 'pw_l'])
    IN[k] = num(D[k][T]);
  for (const k of ['new_day', 'new_week', 'in_asian', 'in_london', 'in_ny']) IN[k] = D[k][T];
  const cr = fns.f_core_update(inp, cs, IN.pd_h, IN.pd_l, IN.pw_h, IN.pw_l, NaN, NaN, true);
  const cx = fns.f_context_update(cinp, ds, cr, cs);
  const f = v => (typeof v === 'number' && Number.isNaN(v) ? null : v);
  lines.push(JSON.stringify({
    levels: cs.levels.map(L => [L.id, L.price, L.role, L.state, L.touches, f(L.wick), L.born_bar, L.in_contact]),
    eqh_pool: cs.eqh_pool, eql_pool: cs.eql_pool,
    struct_dir: cr.struct_dir, bos_bull: cr.bos_bull, bos_bear: cr.bos_bear, choch_bull: cr.choch_bull, choch_bear: cr.choch_bear,
    trend_score: cr.trend_score, swing_conflict: cr.swing_conflict,
    sup: f(cr.nearest_sup_below), sup_id: f(cr.nearest_sup_id), res: f(cr.nearest_res_above), res_id: f(cr.nearest_res_id),
    bull_sweep: cr.bull_sweep, bear_sweep: cr.bear_sweep, bull_sweep_q: cr.bull_sweep_q, bear_sweep_q: cr.bear_sweep_q,
    pdh_swept: cr.pdh_swept, pdl_swept: cr.pdl_swept, pwh_swept: cr.pwh_swept, pwl_swept: cr.pwl_swept,
    eqh_swept: cr.eqh_swept, eql_swept: cr.eql_swept,
    in_asian: cr.in_asian, in_london: cr.in_london, in_ny: cr.in_ny,
    space_ok_bull: cx.space_ok_bull, space_ok_bear: cx.space_ok_bear, struct_ok_bull: cx.struct_ok_bull, struct_ok_bear: cx.struct_ok_bear,
    bull_bos_had_sweep: cx.bull_bos_had_sweep, bear_bos_had_sweep: cx.bear_bos_had_sweep,
    at_sup: cx.at_sup, at_res: cx.at_res, long_zone: cx.long_zone, short_zone: cx.short_zone,
    rej_ok_bull: cx.rej_ok_bull, rej_ok_bear: cx.rej_ok_bear, vol_ok_bull: cx.vol_ok_bull, vol_ok_bear: cx.vol_ok_bear,
    score_bull_pct: cx.score_bull_pct, score_bear_pct: cx.score_bear_pct, gate_fail_bull: cx.gate_fail_bull, gate_fail_bear: cx.gate_fail_bear,
    story_state: cx.story_state,
  }));
}
writeFileSync(outputPath, lines.join('\n') + '\n');
console.log(`${n} candles`);
