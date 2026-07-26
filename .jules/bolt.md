## 2024-10-31 - [Optimize startswith/endswith checks]
**Learning:** Checking string prefixes/suffixes with `any(s.startswith(p) for p in list)` or chained `s.startswith(p1) or s.startswith(p2)` is highly inefficient in Python compared to passing a tuple `s.startswith((p1, p2))`, which is evaluated in C. Using a tuple provides a 10x speedup in hot paths.
**Action:** Replace generator expressions and chained OR statements for `startswith` and `endswith` checks with tuple arguments whenever checking against a static set of strings.
