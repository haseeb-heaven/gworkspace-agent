## 2024-05-13 - String prefix matching optimization
**Learning:** Using multiple `.startswith()` or generator expressions with `any(val.startswith(p) for p in iter)` is significantly slower in Python than passing a static tuple of prefixes to a single `.startswith(tuple)` call, due to C-level optimization in the string method.
**Action:** Replace generator-based `any(val.startswith(p))` and chained `startswith` with tuple-based `.startswith((...))` where multiple prefixes are checked.
