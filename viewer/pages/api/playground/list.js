import fs from 'fs';
import path from 'path';
import { TMP_PLAYGROUND_ROOT } from '../../../lib/serverPaths';
import { getPngPath } from '../../../renderer/index.js';

function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === '.git' || e.name === 'node_modules' || e.name.startsWith('.next')) continue;
      walk(p, out);
    } else if (e.isFile()) {
      out.push(p);
    }
  }
  return out;
}

export default function handler(req, res) {
  try {
    const files = walk(TMP_PLAYGROUND_ROOT);
    const items = files
      .filter((f) => ['.html', '.jsx', '.js'].includes(path.extname(f).toLowerCase()))
      .map((f) => {
        const rel = path.relative(TMP_PLAYGROUND_ROOT, f).replaceAll('\\\\', '/');
        const png = getPngPath(f);
        const pngRel = path.relative(TMP_PLAYGROUND_ROOT, png).replaceAll('\\\\', '/');
        return {
          file: rel,
          png: fs.existsSync(png) ? pngRel : null,
        };
      })
      .sort((a, b) => (a.file > b.file ? 1 : -1));
    res.status(200).json({ root: TMP_PLAYGROUND_ROOT, items });
  } catch (err) {
    res.status(500).json({ error: String(err?.message || err) });
  }
}

