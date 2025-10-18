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
  const { run } = req.query;

  if (!safe(run)) {
    res.status(400).json({ error: 'invalid args' });
    return;
  }

  const runDir = path.join(RESULTS_ROOT, run);
  if (!fs.existsSync(runDir)) {
    res.status(404).json({ error: 'run not found' });
    return;
  }

  try {
    const imageDirs = fs.readdirSync(runDir, { withFileTypes: true })
      .filter(d => d.isDirectory())
      .map(d => ({ name: d.name, path: path.join(runDir, d.name) }));

    let totalFiles = 0;
    let totalWithPng = 0;
    const missingByImage = {};

    for (const imageDir of imageDirs) {
      const targets = walkFiles(imageDir.path, ['.html', '.jsx', '.js']);
      const missing = [];

      for (const f of targets) {
        const png = getPngPath(f);
        if (fs.existsSync(png)) {
          totalWithPng++;
        } else {
          missing.push(path.relative(imageDir.path, f).replaceAll('\\\\', '/'));
        }
      }

      totalFiles += targets.length;
      if (missing.length > 0) {
        missingByImage[imageDir.name] = missing;
      }
    }

    const complete = totalFiles > 0 ? Object.keys(missingByImage).length === 0 : true;
    const missingCount = totalFiles - totalWithPng;

    console.log(`[check-run-pngs] ${run} complete=${complete} total=${totalFiles} withPng=${totalWithPng} missing=${missingCount}`);

    res.status(200).json({
      complete,
      total: totalFiles,
      withPng: totalWithPng,
      missingCount,
      missingByImage
    });
  } catch (err) {
    console.error('Check run PNGs error:', err);
    res.status(500).json({ error: String(err.message || err) });
  }
}
