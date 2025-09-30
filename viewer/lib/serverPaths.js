import path from "path";
import fs from "fs";

export const RESULTS_ROOT = path.resolve(process.cwd(), "..", "results");

// Temporary workspace for the Playground feature
export const TMP_PLAYGROUND_ROOT = path.resolve(process.cwd(), "..", "tmp", "playground");

export function ensureDir(dir) {
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch (_) {}
}

export function ensureWithin(base, target) {
  const rel = path.relative(base, target);
  return !!rel && !rel.startsWith("..") && !path.isAbsolute(rel);
}

export function listDirs(dir) {
  try {
    return fs
      .readdirSync(dir, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => path.join(dir, d.name));
  } catch (_) {
    return [];
  }
}
