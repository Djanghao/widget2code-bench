import path from 'path';
import fs from 'fs';
import { RESULTS_ROOT } from '../../lib/serverPaths';
import { ensureRendered, getPngPath, pngExists } from '../../renderer/index.js';

function safe(s) {
  return s && typeof s === 'string' && !s.includes('..') && !s.includes('\\') && s.length < 512;
}

export default async function handler(req, res) {
  const { run, file } = req.query;

  if (!safe(run) || !safe(file)) {
    res.status(400).json({ error: 'invalid args' });
    return;
  }

  const base = path.join(RESULTS_ROOT, run);
  const filePath = path.resolve(base, file);

  if (!filePath.startsWith(base)) {
    res.status(400).json({ error: 'out of root' });
    return;
  }

  if (!fs.existsSync(filePath)) {
    res.status(404).json({ error: 'file not found' });
    return;
  }

  try {
    const pngPath = getPngPath(filePath);

    if (pngExists(filePath)) {
      res.status(200).json({
        exists: true,
        pngPath: path.relative(base, pngPath).replaceAll('\\', '/')
      });
      return;
    }

    await ensureRendered(filePath);

    res.status(200).json({
      exists: true,
      rendered: true,
      pngPath: path.relative(base, pngPath).replaceAll('\\', '/')
    });
  } catch (err) {
    console.error('Render error:', err);
    res.status(500).json({ error: String(err.message || err) });
  }
}
