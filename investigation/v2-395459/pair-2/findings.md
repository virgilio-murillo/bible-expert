# Findings: NT chapter_study Functionality After OT/NT Generator Split

## Verification Results (All Tested via Runtime Import + AST Analysis)

### 1. Import Integrity — server.py → study_html_generator_nt.py ✅ PASS

server.py imports (lazy, inside `chapter_study` function body):
- `from study_html_generator_nt import gather_chapter_data, generate_study_html` (line 891)
- `from study_html_generator_nt import _generate_patristic_analysis, _generate_grounded_exegetical, _strip_md` (line 936)
- `from unified_html_generator_nt import generate_unified_html` (line 937)

All 6 names (`gather_chapter_data`, `generate_study_html`, `_generate_patristic_analysis`, `_generate_grounded_exegetical`, `_strip_md`, `generate_unified_html`) import successfully at runtime.

### 2. _is_ot() Classification ✅ PASS

- Implementation: `_OT_NAMES = frozenset(BOOKS[i][0] for i in range(1, 40))` → checks `book in _OT_NAMES`
- All 39 OT books (IDs 1-39, Genesis through Malachi) correctly classified as OT.
- All 27 NT books (IDs 40-66, Matthew through Revelation) correctly classified as NOT OT.
- Deuterocanonical books (IDs 67+) are NOT in _OT_NAMES — they would route to NT generator. This may or may not be intentional but is consistent with the current frozenset definition.

### 3. NT Generator (study_html_generator_nt.py) Has All Required Functions ✅ PASS

Functions confirmed present with correct signatures:
- `gather_chapter_data(book: str, chapter: int, version: str, candidates: list) -> dict`
- `generate_study_html(book: str, chapter: int, version: str, chapter_data: dict, geo_data: dict, output_dir: Path) -> Path`
- `_generate_patristic_analysis(book: str, chapter: int, patristic: list) -> str`
- `_generate_grounded_exegetical(book: str, chapter: int, commentaries: dict, morphology: dict) -> str`
- `_strip_md(text: str) -> str`

server.py calls `generate_study_html(book=resolved, chapter=chapter, version=version, chapter_data=chapter_data, geo_data=geo_data, output_dir=out_path)` — matches the 6-parameter signature exactly.

### 4. unified_html_generator_nt.py Signature ✅ PASS

```python
def generate_unified_html(book: str, chapter: int, chapter_data: dict, output_dir: Path) -> Path
```

server.py calls it as `generate_unified_html(resolved, chapter, chapter_data, out_path)` — matches the 4-parameter signature exactly.

### 5. Circular Imports / Missing Dependencies ⚠️ PARTIAL CONCERN

**No circular imports exist.** The dependency chain is linear:
- `server.py` → lazy imports `study_html_generator_nt.py` / `unified_html_generator_nt.py`
- `study_html_generator_nt.py` → only imports `json`, `sqlite3`, `pathlib` at top level; `boto3` lazily
- `unified_html_generator_nt.py` → imports `json`, `sqlite3`, `re`, `unicodedata`, `pathlib`, `collections` at top level

**However:** `unified_html_generator_nt.py` has 5 internal lazy imports from the **original** `study_html_generator.py`:
- Line 67: `from study_html_generator import _s3_cache_get, _s3_cache_put`
- Line 143: `from study_html_generator import _s3_cache_get, _s3_cache_put, _strip_md`
- Line 191: `from study_html_generator import _s3_cache_get`
- Line 208: `from study_html_generator import _s3_cache_get, _s3_cache_put`
- Line 251: `from study_html_generator import _s3_cache_put, _strip_md`

This **works** because `study_html_generator.py` (the original) still exists on disk and exports these symbols. But it means:
- The original `study_html_generator.py` **cannot be deleted** without breaking both unified generators.
- The unified_nt generator depends on a file that "should not be used anymore" per the task context.

`unified_html_generator_ot.py` has the same 5 imports from the original — identical dependency.

### 6. OT Generator (study_html_generator_ot.py) Exports ✅ PASS

All required functions present with correct signatures:
- `gather_chapter_data(book: str, chapter: int, version: str, candidates: list) -> dict`
- `generate_study_html(book: str, chapter: int, version: str, chapter_data: dict, geo_data: dict, output_dir: Path) -> Path`
- `_generate_patristic_analysis(book: str, chapter: int, patristic: list) -> str`
- `_generate_grounded_exegetical(book: str, chapter: int, commentaries: dict, morphology: dict) -> str`
- `_strip_md(text: str) -> str`

OT also has `_translate_lxx` and `_generate_tc_analysis` (additional OT-specific functions not needed by server.py directly).

### 7. Original study_html_generator.py Still Used ⚠️ YES — Cannot Be Removed

| File | Imports from `study_html_generator.py` | Count |
|------|---------------------------------------|-------|
| `server.py` | None (uses _nt/_ot variants) | 0 |
| `study_html_generator_nt.py` | None | 0 |
| `study_html_generator_ot.py` | None | 0 |
| `unified_html_generator_nt.py` | `_s3_cache_get`, `_s3_cache_put`, `_strip_md` | 5 locations |
| `unified_html_generator_ot.py` | `_s3_cache_get`, `_s3_cache_put`, `_strip_md` | 5 locations |

The original `study_html_generator.py` serves as a **shared utility library** for the unified generators. It provides S3 caching functions and `_strip_md`. These 3 functions are also duplicated in both `study_html_generator_nt.py` and `study_html_generator_ot.py` — so the unified generators *could* import from their respective study generators instead, but currently do not.

---

## Summary

| Check | Status | Notes |
|-------|--------|-------|
| Import integrity (server.py → NT) | ✅ PASS | All 6 names import cleanly |
| _is_ot() correctness | ✅ PASS | 39 OT + 27 NT correctly classified |
| NT generator functions | ✅ PASS | All signatures match server.py calls |
| unified_html_generator_nt signature | ✅ PASS | (book, chapter, chapter_data, output_dir) |
| No circular imports | ✅ PASS | Linear dependency chain |
| OT generator functions | ✅ PASS | All signatures match |
| Original file not used | ⚠️ FAIL | unified_*_nt/ot.py both import from it |

## Recommended Fix

The unified generators should import `_s3_cache_get`, `_s3_cache_put`, `_strip_md` from their respective study generators (`study_html_generator_nt` or `study_html_generator_ot`) rather than from the original `study_html_generator.py`. This would allow the original to be safely deleted. The functions are already present in both split files.
