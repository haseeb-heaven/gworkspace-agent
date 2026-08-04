## 2024-06-25 - Using tuple with startswith instead of chained or/generator expressions

**Learning:** Using `str.startswith` or `str.endswith` with a static literal tuple is implemented in C and runs significantly faster than `any()` with a generator or chained `or` conditions. A test revealed a 10x speedup when using a tuple vs a generator comprehension for string prefix checking.

**Action:** Look for instances of `any(s.startswith(x) for x in (...))` or `s.startswith(x) or s.startswith(y)` and replace them with `s.startswith((x, y, ...))` to improve performance, ensuring the argument passed is a static tuple.
