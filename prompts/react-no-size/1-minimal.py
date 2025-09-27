MINIMAL_PROMPT = """
You are an expert front-end developer.
Generate ONE single React component that reproduces the widget UI in the screenshot.

Rules:
- Output ONLY:

export default function Widget() { return (
  /* JSX */
); }

- No imports, no comments, no extra text.
- Root element must be <div className="widget"> … </div>.
"""