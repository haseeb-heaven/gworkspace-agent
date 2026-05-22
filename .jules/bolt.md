## 2024-05-22 - Python startswith with tuple
**Learning:** Using `any(s.startswith(p) for p in [...])` is surprisingly slow due to generator overhead.
**Action:** Always prefer `s.startswith(("prefix1", "prefix2"))` in Python as it's implemented in C and executes significantly faster.
