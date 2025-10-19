import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function runRenderer(scriptName, args) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(__dirname, 'bin', scriptName);
    const proc = spawn('node', [scriptPath, ...args], {
      stdio: 'pipe',
      cwd: process.cwd(),
      detached: false
    });

    let stdout = '';
    let stderr = '';
    let resolved = false;

    const cleanup = () => {
      if (!resolved) {
        resolved = true;
        if (proc.stdout) proc.stdout.removeAllListeners();
        if (proc.stderr) proc.stderr.removeAllListeners();
        proc.removeAllListeners();
      }
    };

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
      console.log(data.toString().trim());
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
      console.error(data.toString().trim());
    });

    proc.on('close', (code) => {
      cleanup();
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        reject(new Error(`Renderer exited with code ${code}: ${stderr}`));
      }
    });

    proc.on('error', (err) => {
      cleanup();
      reject(err);
    });
  });
}

export async function renderJsx(filePath) {
  await runRenderer('render-jsx.mjs', [filePath]);
  return getPngPath(filePath);
}

export async function renderHtml(filePath) {
  await runRenderer('render-html.mjs', [filePath]);
  return getPngPath(filePath);
}

export async function renderJsxBatch(folderPath, concurrency) {
  const args = [folderPath];
  if (concurrency) {
    args.push('-j', String(concurrency));
  }
  await runRenderer('render-jsx-batch.mjs', args);
}

export async function renderHtmlBatch(folderPath, concurrency) {
  const args = [folderPath];
  if (concurrency) {
    args.push('-j', String(concurrency));
  }
  await runRenderer('render-html-batch.mjs', args);
}

export async function cleanPngs(folderPath) {
  await runRenderer('clean.mjs', [folderPath]);
}

export function getPngPath(sourcePath) {
  const parsed = path.parse(sourcePath);
  return path.join(parsed.dir, `${parsed.name}.png`);
}

export function pngExists(sourcePath) {
  const pngPath = getPngPath(sourcePath);
  return fs.existsSync(pngPath);
}

export async function ensureRendered(filePath) {
  if (pngExists(filePath)) {
    return getPngPath(filePath);
  }

  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.jsx' || ext === '.js') {
    return await renderJsx(filePath);
  } else if (ext === '.html') {
    return await renderHtml(filePath);
  } else {
    throw new Error(`Unsupported file type: ${ext}`);
  }
}
