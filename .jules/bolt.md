## 2024-07-16 - [Performance Optimization for startswith checks]
**Learning:** Using chained `.startswith()` conditions or `any(...)` with a generator for multiple string prefixes is slower than passing a static tuple of prefixes to a single `.startswith()` call, which executes in C.
**Action:** Pass a literal tuple to `.startswith()` for better performance when checking multiple prefixes, and include a comment noting the C-level performance benefit.
