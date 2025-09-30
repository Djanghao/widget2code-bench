import fs from "fs";
import path from "path";
import { RESULTS_ROOT } from "../../lib/serverPaths";
import sharp from "sharp";

const THUMBNAIL_SIZE = 120;
const CACHE_DIR = path.join(process.cwd(), ".cache", "thumbnails");

if (!fs.existsSync(CACHE_DIR)) {
  fs.mkdirSync(CACHE_DIR, { recursive: true });
}

export default async function handler(req, res) {
  const { run, file } = req.query;
  if (!safe(run) || !safe(file)) {
    res.status(400).end("bad args");
    return;
  }
  const base = path.join(RESULTS_ROOT, run);
  const abs = path.resolve(base, file);
  if (!abs.startsWith(base)) {
    res.status(400).end("out of root");
    return;
  }
  if (!fs.existsSync(abs)) {
    res.status(404).end("not found");
    return;
  }

  const cacheKey = `${run}_${file.replace(/\//g, "_")}`;
  const cachePath = path.join(CACHE_DIR, `${cacheKey}.webp`);

  if (fs.existsSync(cachePath)) {
    res.setHeader("Content-Type", "image/webp");
    res.setHeader("Cache-Control", "public, max-age=31536000, immutable");
    fs.createReadStream(cachePath).pipe(res);
    return;
  }

  try {
    const thumbnail = await sharp(abs)
      .resize(THUMBNAIL_SIZE, THUMBNAIL_SIZE, { fit: "cover" })
      .webp({ quality: 80 })
      .toBuffer();

    await fs.promises.writeFile(cachePath, thumbnail);

    res.setHeader("Content-Type", "image/webp");
    res.setHeader("Cache-Control", "public, max-age=31536000, immutable");
    res.send(thumbnail);
  } catch (error) {
    console.error("Thumbnail generation failed:", error);
    res.setHeader("Content-Type", "image/png");
    fs.createReadStream(abs).pipe(res);
  }
}

function safe(s) {
  return s && typeof s === "string" && !s.includes("..") && !s.includes("\\") && s.length < 512;
}
