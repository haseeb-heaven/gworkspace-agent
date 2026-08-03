## 2024-07-13 - Performance optimization for startswith/endswith
**Learning:** Checking for multiple string prefixes or suffixes in Python using generator expressions (e.g., `any(val_str.startswith(prefix) for prefix in ["sheet-", ...])`) is slower than using `str.startswith(tuple_of_prefixes)`. The tuple-based `startswith` and `endswith` are implemented in C and evaluate significantly faster.
**Action:** Replace `any(... startswith ...)` and `any(... endswith ...)` patterns with `str.startswith(tuple)` or `str.endswith(tuple)` where applicable to improve performance.
