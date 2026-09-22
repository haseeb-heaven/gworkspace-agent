## 2024-05-24 - Python String Prefix Optimization
**Learning:** Generator expressions with `any(val.startswith(p) for p in iter)` are significantly slower (~10x overhead) compared to C-optimized tuple matching `val.startswith(tuple_of_prefixes)`.
**Action:** Use tuple matching `val.startswith(("prefix1", "prefix2"))` instead of `any()` with list comprehension or `or` chains, ensuring the tuple is defined as a literal to avoid dynamic conversion overhead.
