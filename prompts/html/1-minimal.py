MINIMAL_PROMPT = """
Given a phone widget screenshot, generate ONE single self-contained HTML file that reproduces the widget UI.
Rules:
- Output ONLY HTML code. No explanations, no comments, no extra text.
- Begin exactly with: <html lang="en"> and end exactly with: </html>.
- Place all widget content inside exactly one container: <div class="widget"> ... </div> in the <body>.
- Choose one canvas and match its size exactly:
  S 158×158, M 338×158, or L 338×354.
"""