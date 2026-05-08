## 2026-05-08 - extract_keywords performance improvement
**Learning:** Initializing large sets inside functions that are called repeatedly (like in list filtering) causes unnecessary runtime overhead.
**Action:** Always move static sets (like stop_words) to module-level `frozenset` constants to shift the cost to import-time and improve function execution speed.
