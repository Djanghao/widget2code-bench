import fs from "fs";
import path from "path";
import { RESULTS_ROOT } from "../../lib/serverPaths";

export default function handler(req, res) {
  const { run, image } = req.query;
  if (!isSafe(run) || !isSafe(image)) {
    res.status(400).json({ error: "invalid args" });
    return;
  }
  const base = path.join(RESULTS_ROOT, run, image);
  if (!fs.existsSync(base)) {
    res.status(404).json({ error: "not found" });
    return;
  }
  const categories = {};
  for (const d of fs.readdirSync(base, { withFileTypes: true })) {
    if (d.isDirectory()) {
      const cat = d.name;
      const catDir = path.join(base, cat);
      const files = fs
        .readdirSync(catDir, { withFileTypes: true })
        .filter((f) => f.isFile())
        .map((f) => path.join(catDir, f.name));
      categories[cat] = files
        .map((f) => ({
          name: path.basename(f),
          ext: path.extname(f).toLowerCase(),
          path: path.relative(path.join(RESULTS_ROOT, run), f).replaceAll("\\", "/"),
          code: readText(f),
        }))
        .sort((a, b) => (a.name > b.name ? 1 : -1));
    }
  }
  res.status(200).json({ categories });
}

function isSafe(s) {
  return s && typeof s === "string" && !s.includes("/") && !s.includes("..") && s.length < 256;
}

function readText(p) {
  try {
    return fs.readFileSync(p, "utf8");
  } catch (_) {
    return "";
  }
}
