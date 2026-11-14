#!/usr/bin/env node
// Read-only CLI for the public agentapiai.com API (v1).
// No keys, no writes, no telemetry.

const BASE = (process.env.AGENTAPIAI_API || 'https://agentapiai.com').replace(/\/+$/, '');
const args = process.argv.slice(2);
const cmd = args[0] || 'help';

function flag(name, fallback = '') {
  const i = args.indexOf('--' + name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}
function has(name) { return args.includes('--' + name); }

async function get(path) {
  const url = BASE + path;
  const res = await fetch(url, { headers: { accept: 'application/json' } });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || json.ok === false) {
    const msg = json.error || ('HTTP ' + res.status);
    throw new Error(msg + ' (' + url + ')');
  }
  return json;
}

function pad(s, n) { s = String(s == null ? '' : s); return s.length >= n ? s : s + ' '.repeat(n - s.length); }

function table(rows, cols) {
  const widths = cols.map((c) => Math.max(c.label.length, ...rows.map((r) => String(r[c.key] ?? '').length)));
  console.log(cols.map((c, i) => pad(c.label, widths[i])).join('  '));
  console.log(cols.map((_, i) => '-'.repeat(widths[i])).join('  '));
  for (const r of rows) console.log(cols.map((c, i) => pad(r[c.key], widths[i])).join('  '));
}

async function main() {
  if (cmd === 'sites') {
    const limit = flag('limit', '20');
    const grade = flag('grade', '');
    const q = flag('q', '');
    const sort = flag('sort', 'samples');
    const qs = new URLSearchParams({ limit, sort });
    if (grade) qs.set('grade', grade);
    if (q) qs.set('q', q);
    const d = await get('/v1/sites?' + qs.toString());
    table(d.data, [
      { key: 'grade', label: 'GRADE' }, { key: 'name', label: 'SITE' },
      { key: 'online', label: 'ONLINE' }, { key: 'latency', label: 'LAT' },
      { key: 'samples', label: 'SAMPLES' }, { key: 'slug', label: 'SLUG' },
    ]);
    console.log('\n' + d.meta.total + ' site(s) · dataset ' + (d.meta.datasetVersion || '—'));
    return;
  }
  if (cmd === 'site') {
    const slug = args[1];
    if (!slug) throw new Error('usage: agentapiai-check site <slug>');
    const d = await get('/v1/sites/' + encodeURIComponent(slug));
    console.log(JSON.stringify(d.data, null, 2));
    return;
  }
  if (cmd === 'stats') {
    const d = await get('/v1/stats');
    console.log(JSON.stringify(d.data, null, 2));
    return;
  }
  if (cmd === 'detect') {
    const host = args[1] || flag('host');
    if (!host) throw new Error('usage: agentapiai-check detect <host>');
    try {
      const d = await get('/v1/detect/latest?host=' + encodeURIComponent(host));
      console.log(JSON.stringify(d.data, null, 2));
    } catch (e) {
      if (String(e.message).startsWith('not_found')) {
        console.log('No published detection run for ' + host + '.');
        return;
      }
      throw e;
    }
    return;
  }
  if (cmd === 'reports') {
    const d = await get('/v1/reports');
    table(d.data, [
      { key: 'slug', label: 'SLUG' }, { key: 'model', label: 'MODEL' },
      { key: 'protocol', label: 'PROTOCOL' }, { key: 'verdict', label: 'VERDICT' },
      { key: 'checkedAt', label: 'CHECKED' },
    ]);
    console.log('\n' + d.meta.total + ' published report(s)');
    return;
  }
  console.log(`agentapiai-check 0.1.0 — read-only public data

Usage:
  agentapiai-check sites [--limit 20] [--grade a|b|c] [--q text] [--sort samples|online|latency|price|name]
  agentapiai-check site <slug>
  agentapiai-check stats
  agentapiai-check detect <host>
  agentapiai-check reports

Env:
  AGENTAPIAI_API   override API base (default https://agentapiai.com)

No API key. No writes. Data: /v1/sites, /v1/stats, /v1/reports, /v1/detect/latest.`);
}

main().catch((e) => {
  console.error('error: ' + e.message);
  process.exit(1);
});
