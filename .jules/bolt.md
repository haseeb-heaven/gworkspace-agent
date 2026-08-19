## 2024-05-24 - String startswith optimization
**Learning:** Using a generator expression with `any()` inside `startswith` (e.g., `any(s.startswith(p) for p in prefixes)`) is slow because it creates a new generator object and iterates in Python.
**Action:** Pass a tuple directly to `startswith` (e.g., `s.startswith(("prefix1", "prefix2"))`) to leverage C-optimized prefix matching. Ensure the tuple is created once or provided as a literal.
