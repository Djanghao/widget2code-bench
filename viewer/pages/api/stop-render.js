import { stopRender } from '../../lib/renderManager';

function safe(s) {
  return s && typeof s === 'string' && !s.includes('..') && !s.includes('\\') && s.length < 512;
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  const { run } = req.body;

  if (!run || !safe(run)) {
    res.status(400).json({ error: 'invalid run parameter' });
    return;
  }

  const stopped = stopRender(run);

  if (stopped) {
    res.status(200).json({ success: true, message: 'Render stopped' });
  } else {
    res.status(200).json({ success: false, message: 'No active render found' });
  }
}
