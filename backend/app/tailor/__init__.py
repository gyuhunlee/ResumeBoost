"""Resume tailoring agent.

Pipeline (code does what must be correct, the LLM does what needs judgment):

  parse_resume ─┐
                ├─> agent loop (LLM + tools) ─> user review ─> render ─> save
  analyze_jd ───┘

Deterministic modules: keywords (gap + score), verify (hallucination guard),
formatting (format checks), bank (experience search), render (PDF/DOCX).
LLM modules: parse/jd (with rule-based fallbacks) and agent.
"""
