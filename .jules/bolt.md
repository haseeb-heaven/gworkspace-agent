## 2025-02-26 - Stop Words Optimization in Relevance Search
**Learning:** `extract_keywords` in `gws_assistant/relevance.py` recreated a ~100 item set inside the function for every query.
**Action:** Always check frequently called extraction/filtering functions for locally scoped constants that could be module-level `frozenset` objects to reduce GC and reallocation overhead.
