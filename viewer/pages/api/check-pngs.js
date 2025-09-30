import path from 'path';
import fs from 'fs';
import { RESULTS_ROOT } from '../../lib/serverPaths';
import { getPngPath } from '../../renderer/index.js';

function safe(s) {
  return s && typeof s === 'string' && !s.includes('..') && !s.includes('\\') && s.length < 512;
}

function walkFiles(dir, exts, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === '.git' || e.name === 'node_modules' || e.name.startsWith('.next')) continue;
      walkFiles(p, exts, out);
    } else if (e.isFile()) {
      const ext = path.extname(e.name).toLowerCase();
      if (exts.includes(ext)) out.push(p);
    }
  }
  return out;
}

export default async function handler(req, res) {
  const { run, image } = req.query;

  if (!safe(run) || !safe(image)) {
    res.status(400).json({ error: 'invalid args' });
    return;
  }

  const base = path.join(RESULTS_ROOT, run, image);
  if (!fs.existsSync(base)) {
    res.status(404).json({ error: 'not found' });
    return;
  }

  const targets = walkFiles(base, ['.html', '.jsx', '.js']);
  const missing = [];
  let withPng = 0;
  for (const f of targets) {
    const png = getPngPath(f);
    if (fs.existsSync(png)) {
      withPng += 1;
    } else {
      // Normalize to posix-style paths for client display
      missing.push(path.relative(base, f).replaceAll('\\\\', '/'));
    }
  }

  const complete = targets.length > 0 ? missing.length === 0 : true;
  console.log(`[check-pngs] ${run}/${image} complete=${complete} total=${targets.length} withPng=${withPng} missing=${missing.length}`);
  res.status(200).json({ complete, total: targets.length, withPng, missingCount: missing.length, missing });
}
