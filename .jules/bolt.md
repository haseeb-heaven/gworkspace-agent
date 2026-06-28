## 2024-06-28 - String Prefix/Suffix Checking Performance
**Learning:** Checking multiple string prefixes or suffixes using a generator expression like `any(s.startswith(prefix) for prefix in prefixes)` is significantly slower in Python than passing a tuple directly to `startswith` or `endswith`, because the latter is implemented in C. However, the tuple must be static; dynamically converting a list to a tuple on every call negates the benefit.
**Action:** Always use `str.startswith(tuple_of_prefixes)` or `str.endswith(tuple_of_suffixes)` with static tuples instead of generator expressions.
