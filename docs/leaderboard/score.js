// ThirstMap scorer for the browser: a line-by-line port of thirstmap/scoring.py (parse, score, diagnose, chance)
// plus frontier.parse_batch. tests/test_scorer_parity.py checks that it gives the same verdict as the Python
// scorer on every published reply.
(function (root) {
  'use strict';
  const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const WORDS = { NORTH: 'N', NORTHEAST: 'NE', 'NORTH-EAST': 'NE', EAST: 'E', SOUTHEAST: 'SE', 'SOUTH-EAST': 'SE',
    SOUTH: 'S', SOUTHWEST: 'SW', 'SOUTH-WEST': 'SW', WEST: 'W', NORTHWEST: 'NW', 'NORTH-WEST': 'NW' };

  // Python str()/repr() of a value parsed from JSON, where it matters for matching
  function pyRepr(v) {
    if (v === null) return 'None';
    if (v === true) return 'True';
    if (v === false) return 'False';
    if (typeof v === 'string') return v.includes("'") && !v.includes('"') ? `"${v}"` : `'${v.replace(/'/g, "\\'")}'`;
    if (Array.isArray(v)) return '[' + v.map(pyRepr).join(', ') + ']';
    if (typeof v === 'object') return '{' + Object.entries(v).map(([k, x]) => pyRepr(k) + ': ' + pyRepr(x)).join(', ') + '}';
    if (typeof v === 'number' && Number.isInteger(v) && Math.abs(v) >= 1e21) return BigInt(v).toString();   // Python ints keep every digit
    return String(v);
  }
  const pyStr = v => (typeof v === 'string' ? v : pyRepr(v));
  const stripChars = (s, chars) => { let a = 0, b = s.length;
    while (a < b && chars.includes(s[a])) a++; while (b > a && chars.includes(s[b - 1])) b--; return s.slice(a, b); };
  const isObj = o => o !== null && typeof o === 'object' && !Array.isArray(o);
  const tryJSON = s => { try { return [JSON.parse(s), true]; } catch (e) { return [undefined, false]; } };

  function extractJson(raw) {
    raw = (raw || '').trim();
    let [v, ok] = tryJSON(raw);
    if (ok) return [v, true];
    for (const m of raw.matchAll(/\{[^{}]*\}/gs)) { [v, ok] = tryJSON(m[0]); if (ok) return [v, true]; }
    const m = raw.match(/"answer"\s*:\s*(\[[^\]]*\]|"[^"]*"|-?\d+(?:\.\d+)?|null)/);
    if (m) { [v, ok] = tryJSON(m[1]); if (ok) return [{ answer: v }, false]; }
    return [null, false];
  }
  const escRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  function labels(value, options) {
    if (value === null || value === undefined) return [];
    if (typeof value === 'string') {
      if (['none', 'no', '', '[]'].includes(value.trim().toLowerCase())) return [];
      value = value.split(/[,\s;/]+(?:and\s+)?/);
    }
    const out = [], opts = new Set(options.map(o => String(o).toUpperCase()));
    for (const v of (Array.isArray(value) ? value : [value])) {
      const t = stripChars(pyStr(v).trim(), '"\'.').toUpperCase();
      if (opts.has(t)) out.push(t);
      else for (const o of opts) if (new RegExp(`\\b${escRe(o)}\\b`).test(t)) out.push(o);
    }
    return [...new Set(out)].sort();
  }
  function parse(raw, task) {
    let [obj, ok] = extractJson(raw), value;
    if (isObj(obj) && 'answer' in obj) value = obj.answer; else { value = raw; ok = false; }
    const sc = task.scoring;
    if (sc === 'set') return [labels(value, task.options), ok];
    if (sc === 'choice') { const g = labels(value, task.options); return [g.length === 1 ? g[0] : null, ok && g.length === 1]; }
    if (sc === 'compass') { let t = stripChars(pyStr(value).trim(), '"\'.').toUpperCase().replace(/ /g, ''); t = WORDS[t] || t;
      const good = COMPASS.includes(t); return [good ? t : null, ok && good]; }
    if (sc === 'number') { const m = pyStr(value).match(/-?\d+(?:\.\d+)?/); return [m ? parseFloat(m[0]) : null, ok && !!m]; }
    throw new Error(sc);
  }
  function diagnose(task, pred, parseOk) {
    if (pred === null || (Array.isArray(pred) && pred.length === 0 && task.scoring !== 'set'))
      return parseOk ? ['no_answer'] : ['unparseable_or_no_answer'];
    const tags = [], picked = new Set(Array.isArray(pred) ? pred : [pred]);
    for (const [kind, labs] of Object.entries(task.traps || {})) if (labs.some(l => picked.has(l))) tags.push('trap:' + kind);
    const sc = task.scoring, gold = task.answer;
    if (sc === 'set') {
      if (gold.some(g => !picked.has(g))) tags.push('missed_some');
      if ([...picked].some(p => !gold.includes(p)) && !tags.some(t => t.startsWith('trap:'))) tags.push('extra_unrelated');
    } else if (sc === 'compass') {
      const d = ((COMPASS.indexOf(pred) - COMPASS.indexOf(gold)) % 8 + 8) % 8;
      tags.push(d === 4 ? 'reversed_direction' : (d === 1 || d === 7) ? 'off_by_one_sector' : 'wrong_direction');
    } else if (sc === 'number') tags.push(pred > gold ? 'overestimate' : 'underestimate');
    else if (!tags.length) tags.push('wrong_choice');
    return tags;
  }
  function score(task, raw) {
    const [pred, parseOk] = parse(raw, task), gold = task.answer, sc = task.scoring;
    let correct, credit;
    if (sc === 'set') {
      const g = new Set(gold), p = new Set(pred);
      correct = g.size === p.size && [...g].every(x => p.has(x));
      if (!g.size && !p.size) credit = 1;
      else { const tp = [...g].filter(x => p.has(x)).length, prec = p.size ? tp / p.size : 0, rec = g.size ? tp / g.size : 0;
        credit = prec + rec ? 2 * prec * rec / (prec + rec) : 0; }
    } else if (sc === 'number') { correct = pred !== null && Math.abs(pred - gold) <= task.tolerance; credit = +correct; }
    else { correct = pred === gold; credit = +correct; }
    return { parsed: pred, parse_ok: parseOk, correct: !!correct, credit: Math.round(credit * 1e4) / 1e4,
      tags: correct ? [] : diagnose(task, pred, parseOk) };
  }
  function chance(task) {
    const sc = task.scoring, opts = task.options, gold = task.answer;
    if (sc === 'choice' || sc === 'compass') return 1 / opts.length;
    if (sc === 'set') { const k = gold.length, n = opts.length; return Math.pow(0.35, k) * Math.pow(0.65, n - k); }
    const [lo, hi] = opts; return (Math.min(gold + task.tolerance, hi) - Math.max(gold - task.tolerance, lo)) / (hi - lo);
  }
  function parseBatch(raw) {
    const ms = [...(raw || '').matchAll(/\{[\s\S]*\}/g)].reverse();
    for (const m of ms) { const [o, ok] = tryJSON(m[0]); if (ok && isObj(o)) return o; }
    return {};
  }
  // one-sided binomial test: P(X >= k), X ~ Binomial(n, p)
  function binomGreater(k, n, p) {
    if (k <= 0) return 1;
    const lg = x => { let s = 0; for (let i = 2; i <= x; i++) s += Math.log(i); return s; };
    let tot = 0;
    for (let i = k; i <= n; i++) tot += Math.exp(lg(n) - lg(i) - lg(n - i) + i * Math.log(p) + (n - i) * Math.log(1 - p));
    return Math.min(1, tot);
  }
  const api = { score, parse, diagnose, chance, parseBatch, binomGreater, labels, extractJson };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.TMScore = api;
})(typeof window !== 'undefined' ? window : globalThis);
