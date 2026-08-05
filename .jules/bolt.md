## 2024-05-18 - [Python String startswith/endswith optimization]
**Learning:** Using `any(s.startswith(prefix) for prefix in [list])` is a generator expression that executes significantly slower than passing a literal tuple to `startswith(tuple_of_prefixes)`. The same applies for `.endswith`. This is because passing a tuple to these methods is implemented in C and runs roughly 10x faster.
**Action:** Whenever checking multiple prefixes or suffixes, replace generator expressions with `startswith(literal_tuple)` or `endswith(literal_tuple)`.
