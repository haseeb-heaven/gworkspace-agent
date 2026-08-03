## 2024-05-24 - Tuple startswith/endswith is faster than any()
**Learning:** In Python, passing a tuple of prefixes to str.startswith() or suffixes to str.endswith() is implemented in C and evaluates significantly faster than generator expressions like any(val.startswith(prefix) for prefix in prefixes).
**Action:** Convert any(val.startswith/endswith) to val.startswith(tuple(...)) where the prefixes/suffixes are static.
