## 2024-06-27 - Tuple C-Level Evaluation for String Prefix/Suffix Checking
**Learning:** Using Python's built-in `startswith()` and `endswith()` with a tuple of strings is evaluated in C and executes significantly faster than using a generator expression inside `any()`.
**Action:** Prioritize passing static tuples to `startswith()`/`endswith()` instead of writing `any(s.startswith(p) for p in prefixes)`.
