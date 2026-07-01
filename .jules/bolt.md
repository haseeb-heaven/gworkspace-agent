## 2024-05-18 - [Optimization of any() with startswith]
**Learning:** Using `any(val.startswith(prefix) for prefix in [...])` is significantly slower than passing a tuple directly to `startswith`, i.e., `val.startswith((...))`. The latter is implemented in C and can be ~10x faster.
**Action:** Replace `any(val.startswith(p) for p in [...])` with `val.startswith((...))` whenever multiple static prefixes need to be checked against a string. This applies to multiple instances in the codebase, especially in `gws_assistant/verification_engine.py` and `gws_assistant/langchain_agent.py`.
