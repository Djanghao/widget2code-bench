MINIMAL_PROMPT = """
You are an expert front-end developer.
Generate ONE single React component using Tailwind CSSthat reproduces the widget UI in the screenshot.
Rules:
- Output ONLY:

export default function Widget() { return (
  /* JSX */
); }

- No imports, no comments, no extra text.
- Root element must be <div className="widget …"> … </div>.
- Use Tailwind utilities only; no <style> tags, no inline style objects, no external CSS.
"""