# Findings: NT Chapter Study Functionality After OT/NT Generator Split

## Verification Results

### 1. Import integrity — ✅ PASS
`server.py` successfully imports all required names from `study_html_generator_nt.py`:
- `gather_chapter_data` (line 891)
- `generate_study_html` (line 891)
- `_generate_patristic_analysis` (line 936)
- `_generate_grounded_exegetical` (line 936)
- `_strip_md` (line 936)
- `generate_unified_html` from `unified_html_generator_nt.py` (line 937)

All imports confirmed via runtime test — zero ImportError.

### 2. _is_ot() classification — ✅ PASS
`_is_ot()` at server.py:15 uses `_OT_NAMES = frozenset(BOOKS[i][0] for i in range(1, 40))` — exactly IDs 1-39 (Genesis through Malachi). Runtime test confirms 39 OT + 27 NT = 66 books.

### 3. NT generator has all required background functions — ✅ PASS
`study_html_generator_nt.py` exports:
- `gather_chapter_data` (line 39)
- `_strip_md` (line 322)
- `_generate_patristic_analysis` (line 410)
- `_generate_grounded_exegetical` (line 541)
- `generate_study_html` (line 605)

### 4. unified_html_generator_nt.py signature — ✅ PASS
`generate_unified_html(book: str, chapter: int, chapter_data: dict, output_dir: Path) -> Path` (line 65).
Server calls it with exactly these 4 positional args: `generate_unified_html(resolved, chapter, chapter_data, out_path)` at line ~968.

### 5. No circular imports — ✅ PASS
Import chain verified:
- `server.py` → `study_html_generator_nt.py` (lazy, inside function)
- `server.py` → `unified_html_generator_nt.py` (lazy, inside function)
- `unified_html_generator_nt.py` → `study_html_generator.py` (for `_s3_cache_get`, `_s3_cache_put`, `_strip_md` only)
- No circular dependency — the old `study_html_generator.py` doesn't import from any of the new split files.

### 6. OT generator exports all required functions — ✅ PASS
`study_html_generator_ot.py` exports identical set:
- `gather_chapter_data` (line 39)
- `_strip_md` (line 372)
- `_generate_patristic_analysis` (line 507)
- `_generate_grounded_exegetical` (line 638)
- `generate_study_html` (line 702)

`unified_html_generator_ot.py` has `generate_unified_html(book, chapter, chapter_data, output_dir)` at line 65 — same signature as NT.

### 7. Old study_html_generator.py usage — ⚠️ STILL USED (intentionally)
- `server.py` does **NOT** import from `study_html_generator.py` — confirmed by grep.
- However, BOTH `unified_html_generator_nt.py` and `unified_html_generator_ot.py` import `_s3_cache_get`, `_s3_cache_put`, `_strip_md` from it (5 occurrences each, all lazy inside functions).
- The old file **MUST NOT be deleted** — it serves as a shared utility module for S3 caching.
- There's also an old `unified_html_generator.py` (no suffix) that still exists but is NOT imported by server.py.

## Issues Found

### Issue A: SyntaxWarning in study_html_generator_ot.py (minor)
Lines 1611 and 1615 have `"\."` which is an invalid escape sequence. Should be `r"\."` or `"\\."`. Non-blocking but will become an error in future Python versions.

### Issue B: Old generator used as utility (architectural debt)
Both unified generators depend on `study_html_generator.py` for S3 cache helpers. This creates a hidden dependency — if someone deletes the "old" file thinking it's unused, both unified generators break. Recommend extracting `_s3_cache_get`, `_s3_cache_put`, `_strip_md` into a dedicated `cache_utils.py`.

## Summary

| Check | Status |
|-------|--------|
| Import integrity (NT) | ✅ PASS |
| _is_ot() classification | ✅ PASS |
| NT background functions | ✅ PASS |
| unified_html_generator_nt signature | ✅ PASS |
| No circular imports | ✅ PASS |
| OT generator exports | ✅ PASS |
| Old generator not directly used by server.py | ✅ PASS |
| Old generator still needed by unified_* | ⚠️ Architectural debt |
| SyntaxWarning in OT generator | ⚠️ Minor |

**Verdict: NT chapter_study functionality is correctly wired after the split. All imports resolve, all signatures match, routing logic is sound.**
