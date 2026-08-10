## 2024-05-24 - Optimize string prefix checking
**Learning:** Using `str.startswith(tuple_of_prefixes)` is significantly faster than using generator expressions like `any(str.startswith(prefix) for prefix in [...])` because the tuple passing is implemented directly in C, avoiding Python's generator iteration overhead.
**Action:** Whenever checking multiple prefixes or suffixes against a string, pass a static literal tuple directly to `startswith()` or `endswith()`.
