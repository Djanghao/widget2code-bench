import fs from 'fs';
import path from 'path';
import { TMP_PLAYGROUND_ROOT } from '../../../lib/serverPaths';

const MIME = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.html': 'text/html; charset=utf-8',
  '.jsx': 'text/plain; charset=utf-8',
  '.js': 'text/plain; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
};

function safeRel(s) {
  return s && typeof s === 'string' && !s.includes('..') && !s.includes('\\') && s.length < 1024;
}

export default function handler(req, res) {
  const { file } = req.query;
  if (!safeRel(file)) {
    res.status(400).end('bad args');
    return;
  }
  const base = TMP_PLAYGROUND_ROOT;
  const abs = path.resolve(base, file);
  if (!abs.startsWith(base)) {
    res.status(400).end('out of root');
    return;
  }
  if (!fs.existsSync(abs)) {
    res.status(404).end('not found');
    return;
  }
  const ext = path.extname(abs).toLowerCase();
  res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream');
  fs.createReadStream(abs).pipe(res);
}

