import fs from 'fs';
import path from 'path';
import { TMP_PLAYGROUND_ROOT, ensureDir } from '../../../lib/serverPaths';

export const config = {
  api: {
    bodyParser: false,
  },
};

function safeRel(s) {
  if (!s || typeof s !== 'string') return null;
  if (s.includes('..') || s.includes('\\')) return null;
  // normalize to posix-like separators for consistency
  return s.replaceAll('\\\\', '/');
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  // Use a simple streaming parser to avoid extra deps if possible.
  // However, Next API lacks built-in multipart; rely on dynamic import of formidable to keep footprint small.
  let formidable;
  try {
    formidable = (await import('formidable')).default;
  } catch (err) {
    res.status(500).json({ error: 'formidable not installed' });
    return;
  }

  ensureDir(TMP_PLAYGROUND_ROOT);

  const form = formidable({ multiples: true, keepExtensions: true });

  form.parse(req, (err, fields, files) => {
    if (err) {
      res.status(500).json({ error: String(err?.message || err) });
      return;
    }
    try {
      const incoming = [];
      const list = Array.isArray(files.file) ? files.file : files.file ? [files.file] : [];
      // Accept arbitrary file field names as well
      if (list.length === 0) {
        for (const key of Object.keys(files)) {
          const arr = Array.isArray(files[key]) ? files[key] : [files[key]];
          for (const f of arr) list.push(f);
        }
      }

      for (const f of list) {
        const rel = safeRel((f.originalFilename && fields?.relativePath) ? String(fields.relativePath) : (f.originalFilename || f.newFilename));
        // Support rc-upload/data callback supplying relativePath per file: relativePath[]
        let relPath = rel;
        if (!relPath) {
          const fieldRel = fields?.relativePath || fields?.path || fields?.targetPath;
          relPath = safeRel(Array.isArray(fieldRel) ? fieldRel[0] : fieldRel);
        }
        if (!relPath) relPath = safeRel(f.originalFilename || f.newFilename);
        if (!relPath) continue;
        const dest = path.resolve(TMP_PLAYGROUND_ROOT, relPath);
        if (!dest.startsWith(TMP_PLAYGROUND_ROOT)) continue;
        ensureDir(path.dirname(dest));
        fs.copyFileSync(f.filepath || f._writeStream?.path || f.path, dest);
        incoming.push({ relativePath: path.relative(TMP_PLAYGROUND_ROOT, dest).replaceAll('\\\\', '/') });
      }

      res.status(200).json({ ok: true, files: incoming });
    } catch (e) {
      res.status(500).json({ error: String(e?.message || e) });
    }
  });
}

