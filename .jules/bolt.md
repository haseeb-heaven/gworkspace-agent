## 2024-05-24 - Optimize startswith with tuples
**Learning:** Using `any(s.startswith(p) for p in prefixes)` introduces unnecessary Python generator overhead. Passing a static tuple directly to `startswith()` pushes the iteration to C, evaluating significantly faster.
**Action:** Always use `str.startswith(tuple_of_prefixes)` instead of generator expressions for multiple prefix checks. Ensure the tuple is a static literal to avoid list-to-tuple conversion overhead.
