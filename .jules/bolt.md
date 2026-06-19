## 2024-06-19 - Fast string prefix matching
**Learning:** Checking multiple string prefixes using generator expressions (`any(s.startswith(p) for p in [a, b])`) or chained ORs (`s.startswith(a) or s.startswith(b)`) is much slower than using a tuple (`s.startswith((a, b))`) because the tuple version is implemented in C.
**Action:** Replace `any(... startswith ...)` and chained `.startswith()` with `.startswith(tuple_of_prefixes)` when dealing with multiple prefixes in performance critical areas.
