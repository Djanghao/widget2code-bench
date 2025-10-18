import path from 'path';
import fs from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
import { RESULTS_ROOT } from '../../lib/serverPaths';

const execAsync = promisify(exec);

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
    const scriptPath = path.resolve(process.cwd(), '..', 'scripts', 'check_results.py');
    const pythonPath = path.resolve(process.cwd(), '..', 'venv', 'bin', 'python');

    const cmd = `"${pythonPath}" "${scriptPath}" "${runDir}" --json`;

    const { stdout, stderr } = await execAsync(cmd, {
      maxBuffer: 10 * 1024 * 1024
    });

    if (stderr && stderr.trim()) {
      console.error('Check run stderr:', stderr);
    }

    try {
      const result = JSON.parse(stdout);
      res.status(200).json(result);
    } catch (parseErr) {
      console.error('Failed to parse check_results output:', parseErr);
      console.error('Output was:', stdout);
      res.status(500).json({ error: 'Failed to parse check results' });
    }
  } catch (err) {
    console.error('Check run error:', err);
    res.status(500).json({ error: String(err.message || err) });
  }
}
