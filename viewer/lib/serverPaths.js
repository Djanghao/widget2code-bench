import path from "path";
import fs from "fs";

export const RESULTS_ROOT = path.resolve(process.cwd(), "..", "results");

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

