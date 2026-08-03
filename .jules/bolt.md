
## 2024-06-12 - [Python Optimization]
**Learning:** Using generator expressions like `any(val.startswith(prefix) for prefix in [...])` is significantly slower than passing a tuple directly to `startswith`, e.g., `val.startswith((...))`, because the tuple approach is implemented in C.
**Action:** Always prefer `startswith(tuple)` over `any()` with `startswith` for static prefix lists to maximize performance.
