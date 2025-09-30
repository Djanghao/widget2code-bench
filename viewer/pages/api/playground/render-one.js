import path from 'path';
import fs from 'fs';
import { TMP_PLAYGROUND_ROOT } from '../../../lib/serverPaths';
import { ensureRendered, getPngPath } from '../../../renderer/index.js';

function safeRel(s) {
  return s && typeof s === 'string' && !s.includes('..') && !s.includes('\\') && s.length < 1024;
}

export default async function handler(req, res) {
  const { file } = req.query;
  if (!safeRel(file)) {
    res.status(400).json({ error: 'invalid args' });
    return;
  }
  const base = TMP_PLAYGROUND_ROOT;
  const abs = path.resolve(base, file);
  if (!abs.startsWith(base)) {
    res.status(400).json({ error: 'out of root' });
    return;
  }
  if (!fs.existsSync(abs)) {
    res.status(404).json({ error: 'not found' });
    return;
  }
  try {
    await ensureRendered(abs);
    const pngRel = path.relative(base, getPngPath(abs)).replaceAll('\\\\', '/');
    res.status(200).json({ ok: true, png: pngRel });
  } catch (err) {
    res.status(500).json({ error: String(err?.message || err) });
  }
}

