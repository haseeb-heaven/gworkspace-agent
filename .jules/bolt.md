## 2024-05-14 - String prefix optimization
**Learning:** Found several generator expressions with `.startswith()` such as `any(val_str.startswith(prefix) for prefix in [...])`
**Action:** Replace these with tuple passing directly to `startswith` e.g., `val_str.startswith(("prefix1", "prefix2"))` since it's C-optimized and much faster.
