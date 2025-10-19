import { isRenderActive } from '../../lib/renderManager';

function safe(s) {
  return s && typeof s === 'string' && !s.includes('..') && !s.includes('\\') && s.length < 512;
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  const { run } = req.query;

  if (!run || !safe(run)) {
    res.status(400).json({ error: 'invalid run parameter' });
    return;
  }

  const isActive = isRenderActive(run);
  res.status(200).json({ isRendering: isActive });
}
