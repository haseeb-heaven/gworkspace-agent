## 2024-05-18 - String prefix checking optimization
**Learning:** Python's `str.startswith()` supports tuple arguments natively, which is C-optimized. Using `any(val.startswith(p) for p in iterable)` or long chains of `or` is ~3-10x slower than converting the prefixes to a single static tuple and using `val.startswith((prefix1, prefix2))`.
**Action:** Replace `any(...)` and long `or` chains for `startswith` checks with a single `startswith(tuple)` call for better performance.
