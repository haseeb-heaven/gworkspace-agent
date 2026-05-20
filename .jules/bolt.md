## 2024-06-18 - Fast Prefix Checking with `startswith`
**Learning:** Checking against multiple prefixes using `any(val.startswith(p) for p in [...])` is relatively slow because it constructs a Python generator and iterates in the interpreter layer.
**Action:** Use the natively supported `str.startswith((p1, p2, ...))` with a tuple instead. This delegates the loop iteration entirely to the underlying C implementation, yielding an approximate 10x performance improvement for prefix checks.
