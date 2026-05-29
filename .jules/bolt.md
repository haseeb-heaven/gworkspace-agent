## $(date +%Y-%m-%d) - Optimize startswith tuple evaluation
**Learning:** Checking for multiple prefixes using a generator expression like `any(s.startswith(p) for p in prefixes)` evaluates much slower than `s.startswith(tuple(prefixes))` because passing a tuple to `startswith` is implemented natively in C.
**Action:** Always prefer `startswith(tuple)` or `endswith(tuple)` over loop constructs or `any()` when checking against multiple string prefixes or suffixes. Keep an eye out for generator expressions masking what could be a C-level optimization.
