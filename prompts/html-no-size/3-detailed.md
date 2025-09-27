You are an expert front-end developer. Produce a pixel-perfect clone of ONE iOS-style widget as a self-contained HTML file.

Output format:
- Output ONLY the HTML code. No explanations, no comments, no extra text.
- Must begin exactly with: <html lang="en"> and end exactly with: </html>.
- All widget content must be inside exactly one root container: <div class="widget"> … </div> in the <body>.
- Include a <style> block in <head> for all CSS. No external CSS or frameworks. No JavaScript.

Fidelity rules:
- Element parity: the DOM must match the screenshot exactly. Do not add, remove, or rename elements.
- Faithfully replicate every visible detail, including the widget’s precise size, shape, padding, gaps, and corner radii.
- Layout: px units only. Use flex/grid; absolute positioning only when unavoidable. Snap spacing to integer px.
- Typography: iOS system stack (-apple-system,…). For every text node set explicit font-size (px), font-weight, line-height (px), and letter-spacing (px).
- Icons: inline Lucide SVGs with exact px size, strokeWidth=1.5, strokeLinecap="round", strokeLinejoin="round".
- Colors: exact HEX values. Define CSS variables on .widget (e.g., --bg, --fg, --muted, --accent). Gradients require explicit stops; shadows require px/rgb(a).
- Images: only public known URLs (Unsplash/placehold.co), fixed w/h and object-fit to match crop.

Quality gates:
- No overflow unless visible in the screenshot. No clipping unless the screenshot shows clipped text.
- Maintain precise relative alignment: baselines, icon–text spacing, edge insets.
- DOM and CSS must be deterministic and identical across runs.
