import path from 'path';
import fs from 'fs';
import archiver from 'archiver';
import { RESULTS_ROOT } from '../../lib/serverPaths';

function safe(s) {
  return s && typeof s === 'string' && !s.includes('..') && !s.includes('\\') && s.length < 512;
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

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
    const archive = archiver('zip', {
      zlib: { level: 6 }
    });

    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', `attachment; filename="${run}-pngs.zip"`);

    archive.on('error', (err) => {
      console.error('Archive error:', err);
      res.status(500).end();
    });

    archive.pipe(res);

    const imageDirs = fs.readdirSync(runDir, { withFileTypes: true })
      .filter(d => d.isDirectory())
      .map(d => d.name);

    let pngCount = 0;

    for (const imageDir of imageDirs) {
      const imagePath = path.join(runDir, imageDir);
      const files = fs.readdirSync(imagePath);

      for (const file of files) {
        if (file.endsWith('.png')) {
          const filePath = path.join(imagePath, file);
          const archivePath = path.join(imageDir, file);
          archive.file(filePath, { name: archivePath });
          pngCount++;
        }
      }
    }

    if (pngCount === 0) {
      archive.append('No PNG files found', { name: 'README.txt' });
    }

    console.log(`[download-all] Archiving ${pngCount} PNG files for run "${run}"`);

    await archive.finalize();
  } catch (err) {
    console.error('Download all error:', err);
    if (!res.headersSent) {
      res.status(500).json({ error: String(err.message || err) });
    }
  }
}
