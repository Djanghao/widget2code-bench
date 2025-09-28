You are an expert front-end developer.
Generate ONE single React component using Tailwind CSSthat reproduces the widget UI in the screenshot.
Rules:
- Output ONLY:

<zero or more import lines for required components>

export default function Widget() { return (
  /* JSX */
); }

- No comments, no extra text.
- Always import all external components used in the JSX, and nothing else.
- Root element must be <div className="widget …"> … </div>.
- Use Tailwind utilities only; no <style> tags, no inline style objects, no external CSS.
