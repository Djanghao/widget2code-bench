import fs from "fs";
import path from "path";
import { RESULTS_ROOT, listDirs } from "../../lib/serverPaths";

export default function handler(req, res) {
  try {
    const dirs = listDirs(RESULTS_ROOT);
    const runs = dirs
      .map((dir) => {
        const name = path.basename(dir);
        const metaPath = path.join(dir, "run.meta.json");
        let meta = null;
        try {
          meta = JSON.parse(fs.readFileSync(metaPath, "utf8"));
        } catch (_) {}
        const stat = fs.statSync(dir);
        return {
          name,
          created_at: meta?.created_at || new Date(stat.mtimeMs).toISOString(),
          experiment: meta?.experiment || null,
          model: meta?.model || null,
          count: countImages(dir),
        };
      })
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
    res.status(200).json({ root: RESULTS_ROOT, runs });
  } catch (e) {
    res.status(200).json({ root: RESULTS_ROOT, runs: [] });
  }
}

function countImages(dir) {
  try {
    return fs
      .readdirSync(dir, { withFileTypes: true })
      .filter((d) => d.isDirectory() && d.name !== ".git")
      .length;
  } catch (_) {
    return 0;
  }
}
