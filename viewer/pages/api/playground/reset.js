import fs from 'fs';
import path from 'path';
import { TMP_PLAYGROUND_ROOT, ensureDir } from '../../../lib/serverPaths';

function rimraf(dir) {
  try {
    if (!fs.existsSync(dir)) return;
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) rimraf(p);
      else fs.unlinkSync(p);
    }
    fs.rmdirSync(dir);
  } catch (_) {}
}

export default function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  try {
    rimraf(TMP_PLAYGROUND_ROOT);
    ensureDir(TMP_PLAYGROUND_ROOT);
    res.status(200).json({ ok: true, root: TMP_PLAYGROUND_ROOT });
  } catch (err) {
    res.status(500).json({ error: String(err?.message || err) });
  }
}

