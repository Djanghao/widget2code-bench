import fs from "fs";
import path from "path";
import { RESULTS_ROOT } from "../../lib/serverPaths";

export default function handler(req, res) {
  const { run } = req.query;
  if (!run || typeof run !== "string" || run.includes("/") || run.includes("..")) {
    res.status(400).json({ error: "invalid run" });
    return;
  }
  const runDir = path.join(RESULTS_ROOT, run);
  if (!fs.existsSync(runDir)) {
    res.status(404).json({ error: "run not found" });
    return;
  }
  const items = [];
  for (const d of fs.readdirSync(runDir, { withFileTypes: true })) {
    if (!d.isDirectory()) continue;
    if (d.name === ".git") continue;
    const imageDir = path.join(runDir, d.name);
    const src = findSource(imageDir);
    items.push({ id: d.name, source: src ? `${d.name}/${path.basename(src)}` : null });
  }
  items.sort((a, b) => (a.id > b.id ? 1 : -1));
  res.status(200).json({ images: items });
}

function findSource(dir) {
  const exts = [".png", ".jpg", ".jpeg", ".webp"];
  for (const e of exts) {
    const p = path.join(dir, `source${e}`);
    if (fs.existsSync(p)) return p;
  }
  return null;
}
