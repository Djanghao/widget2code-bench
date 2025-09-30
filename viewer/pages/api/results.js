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
  const runMeta = readRunMeta(path.join(RESULTS_ROOT, run, "run.meta.json"));
  const promptsRoot = runMeta?.prompts_root;
  const categories = {};
  for (const d of fs.readdirSync(base, { withFileTypes: true })) {
    if (d.isDirectory()) {
      const cat = d.name;
      const catDir = path.join(base, cat);
      // Only include renderable source files; exclude generated PNGs and misc files
      const allowed = new Set([".html", ".jsx", ".js"]);
      const files = fs
        .readdirSync(catDir, { withFileTypes: true })
        .filter((f) => f.isFile())
        .map((f) => path.join(catDir, f.name))
        .filter((f) => allowed.has(path.extname(f).toLowerCase()));

      categories[cat] = files
        .map((f) => ({
          name: path.basename(f, path.extname(f)),
          ext: path.extname(f).toLowerCase(),
          path: path.relative(path.join(RESULTS_ROOT, run), f).replaceAll("\\", "/"),
          code: readText(f),
          prompt: readPrompt(promptsRoot, cat, path.basename(f, path.extname(f))),
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

function readRunMeta(p) {
  try {
    const raw = fs.readFileSync(p, "utf8");
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

function readPrompt(root, category, name) {
  if (!root || !category || !name) return null;
  if (category.includes("..") || category.includes("\\")) return null;
  const base = path.resolve(root);
  const file = path.resolve(base, category, `${name}.md`);
  if (!file.startsWith(base)) return null;
  try {
    return fs.readFileSync(file, "utf8");
  } catch (_) {
    return null;
  }
}
