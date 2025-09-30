import fs from 'fs';
import path from 'path';
import { TMP_PLAYGROUND_ROOT, ensureDir } from '../../../lib/serverPaths';

function safeRel(s) {
  return s && typeof s === 'string' && !s.includes('..') && !s.includes('\\') && s.length < 512;
}

export default function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  try {
    const { file, content } = req.body || {};
    if (!safeRel(file) || typeof content !== 'string') {
      res.status(400).json({ error: 'bad args' });
      return;
    }
    const dest = path.resolve(TMP_PLAYGROUND_ROOT, file);
    if (!dest.startsWith(TMP_PLAYGROUND_ROOT)) {
      res.status(400).json({ error: 'out of root' });
      return;
    }
    ensureDir(path.dirname(dest));
    fs.writeFileSync(dest, content, 'utf8');
    res.status(200).json({ ok: true, file });
  } catch (err) {
    res.status(500).json({ error: String(err?.message || err) });
  }
}

