# AI - AI + Analysis team

Planned modules: `summary.py`, `chatbot.py`, `tools.py`, `number_guard.py`.
`providers/` is reserved for future Ollama/Groq integration when needed.
Use reviewed deterministic calculation results; no raw file input to providers.
Numeric claims must match tool outputs and traceable sources; reject/retry invalid
answers and include a financial-advice disclaimer. Mock providers in `tests/ai/`.
No provider, LangChain/LangGraph workflow or tool implementation is added yet.
