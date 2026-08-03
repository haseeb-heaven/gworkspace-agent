## 2024-05-24 - Python Tuple Prefix Checking
**Learning:** Using `any(val.startswith(prefix) for prefix in [...])` or chaining `or` conditions with `startswith` is slower because of generator overhead and multiple function calls. Passing a tuple of prefixes to `startswith`, like `val.startswith(("prefix1", "prefix2"))`, is implemented in C and evaluates significantly faster.
**Action:** When checking for multiple string prefixes, always prefer using `str.startswith(tuple_of_prefixes)`.
