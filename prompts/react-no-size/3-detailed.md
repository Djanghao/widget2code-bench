You are an expert front-end developer. Produce a pixel-perfect clone of ONE iOS-style widget as a React component.

Output format:
export default function Widget() { return (
  /* JSX only */
); }

Hard rules:
- Output ONLY the component above. No imports, no comments, no extra text.
- Root must be a single <div className="widget"> … </div>.
- Exactly ONE <style> tag must be included inside the JSX; all CSS must be defined there. No external CSS or Tailwind.
- Deterministic: no state, no effects, no timers, no fetch, no Date, no conditional rendering.

Fidelity rules:
- Element parity: DOM must match the screenshot exactly. Do not add, remove, or rename elements.
- The number of elements must match the screenshot exactly.
- Layout: px units only; use flex/grid; absolute only if essential. Snap spacing to integer px.
- Typography: iOS system stack (-apple-system,…). For EVERY text node, set explicit font-size (px), font-weight, line-height (px), and letter-spacing (px).
- Icons: lucide-react components (<Sun/>, …) with explicit size (px), strokeWidth={1.5}, strokeLinecap="round", strokeLinejoin="round". If no exact match, choose the closest semantic icon only.
- Colors: exact HEX values. Define CSS variables on .widget (--bg, --fg, --accent, etc.). Gradients require explicit stops; shadows require px/rgb(a).
- Images: only public known URLs (Unsplash/placehold.co) with fixed w/h and object-fit to match crop.
- Faithfully replicate every visible detail from the screenshot.

Quality gates:
- No unintended overflow or clipping. Clip text only if it appears clipped in the screenshot.
- Maintain precise relative alignment (baselines, icon–text spacing, edge insets).
- DOM and CSS must be deterministic and identical across runs.
