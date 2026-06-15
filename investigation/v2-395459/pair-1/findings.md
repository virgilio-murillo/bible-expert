# Findings: NT chapter_study Generator Split Verification

Investigation date: 2026-06-14T21:57 CST

## 1. Import Integrity — server.py → study_html_generator_nt.py

**PASS.** `server.py` imports the following from `study_html_generator_nt`:
- `gather_chapter_data` (line 891) — exists at line 39
- `generate_study_html` (line 891) — exists at line 605
- `_generate_patristic_analysis` (line 936) — exists at line 410
- `_generate_grounded_exegetical` (line 936) — exists at line 541
- `_strip_md` (line 936) — exists at line 322

All five names are exported by `study_html_generator_nt.py`.

## 2. Import Integrity — server.py → unified_html_generator_nt.py

**PASS.** `server.py` imports `generate_unified_html` (line 937) — exists at line 65 with signature:
```python
def generate_unified_html(book: str, chapter: int, chapter_data: dict, output_dir: Path) -> Path:
```
This matches the call pattern in server.py where it's invoked as `generate_unified_html(resolved, chapter, chapter_data, out_path)`.

## 3. _is_ot() Classification

**PASS.** Implementation at server.py lines 12-17:
```python
_OT_NAMES = frozenset(BOOKS[i][0] for i in range(1, 40))
def _is_ot(book: str) -> bool:
    return book in _OT_NAMES
```
- `range(1, 40)` yields IDs 1-39 inclusive → Genesis through Malachi (verified in books.py)
- IDs 40-66 (Matthew through Revelation) are NOT in `_OT_NAMES` → correctly classified as NT
- Deuterocanonical (67+) and Apostolic Fathers (80+) are also NOT in `_OT_NAMES` → will route to NT generator (potential concern — see claim 8)

## 4. unified_html_generator_nt.py Signature

**PASS.** Signature: `generate_unified_html(book: str, chapter: int, chapter_data: dict, output_dir: Path) -> Path` at line 65. Matches the 4-argument call in server.py (line ~968 via `generate_unified_html(resolved, chapter, chapter_data, out_path)`).

## 5. CRITICAL BUG — unified_html_generator_nt.py Still Imports from Original study_html_generator.py

**FAIL.** `unified_html_generator_nt.py` has 5 internal imports from the ORIGINAL `study_html_generator` module:
- Line 67: `from study_html_generator import _s3_cache_get, _s3_cache_put`
- Line 143: `from study_html_generator import _s3_cache_get, _s3_cache_put, _strip_md`
- Line 191: `from study_html_generator import _s3_cache_get`
- Line 208: `from study_html_generator import _s3_cache_get, _s3_cache_put`
- Line 251: `from study_html_generator import _s3_cache_put, _strip_md`

These should import from `study_html_generator_nt` instead. Currently this WORKS because `study_html_generator.py` (the original 84KB file) still exists on disk and has all those functions. But:
- It defeats the purpose of the split
- If `study_html_generator.py` is ever deleted, the NT unified generator will break
- It means `unified_html_generator_nt.py` is just an unmodified copy of `unified_html_generator.py`

**Same issue exists in `unified_html_generator_ot.py`** — it also imports from `study_html_generator` instead of `study_html_generator_ot`.

## 6. OT Generator Exports

**PASS.** `study_html_generator_ot.py` exports all required functions:
- `gather_chapter_data` (line 39) — same signature as NT: `(book, chapter, version, candidates) -> dict`
- `generate_study_html` (line 702) — same signature as NT: `(book, chapter, version, chapter_data, geo_data, output_dir) -> Path`
- `_generate_patristic_analysis` (line 507)
- `_generate_grounded_exegetical` (line 638)
- `_strip_md` (line 372)
- `_s3_cache_get` (line 9), `_s3_cache_put` (line 21)

`unified_html_generator_ot.py` exports `generate_unified_html` at line 65 with matching signature.

## 7. Original study_html_generator.py Usage in server.py

**PASS.** `server.py` does NOT import from `study_html_generator` (the original). All 6 import statements reference only the `_ot` or `_nt` suffixed modules. The original file is no longer directly used by server.py.

## 8. No Circular Imports

**PASS.** Dependency graph is one-directional:
- `server.py` → `study_html_generator_{ot,nt}.py` (for gather/generate/patristic/exegetical)
- `server.py` → `unified_html_generator_{ot,nt}.py` (for unified HTML)
- `unified_html_generator_{ot,nt}.py` → `study_html_generator.py` (for cache/strip — BUG from claim 5)
- Neither `study_html_generator_nt` nor `study_html_generator_ot` imports from any unified generator

No circular dependency exists.

## 9. File Identity Confirmation

**CONFIRMED:** `study_html_generator_nt.py` (84,158 bytes) = exact copy of `study_html_generator.py` (84,158 bytes). This is consistent with "reverted to working May 12 state" — the NT version IS the original working code.

Similarly `unified_html_generator_nt.py` (50,029 bytes) = exact copy of `unified_html_generator.py` (50,029 bytes).

## 10. Functional Correctness of NT Path

**PASS (with caveat from claim 5).** The NT flow is:
1. User calls `chapter_study(book="Matthew", chapter=1, ...)`
2. `_is_ot("Matthew")` → False → imports from `study_html_generator_nt`
3. `gather_chapter_data` runs, gathers verses + parallel + patristic + xrefs + morphology + greek_commentaries
4. `generate_study_html` produces interactive HTML, opens it
5. Background thread imports `_generate_patristic_analysis`, `_generate_grounded_exegetical`, `_strip_md` from `study_html_generator_nt`
6. Background thread imports `generate_unified_html` from `unified_html_generator_nt`
7. `generate_unified_html` internally imports `_s3_cache_get`/`_s3_cache_put`/`_strip_md` from... `study_html_generator` (the original — BUG)

As long as `study_html_generator.py` remains on disk, this works. If deleted, step 7 breaks.

---

## Summary

| Check | Result |
|-------|--------|
| 1. Import integrity (server → NT study) | ✅ PASS |
| 2. Import integrity (server → NT unified) | ✅ PASS |
| 3. _is_ot() classification | ✅ PASS |
| 4. unified_html_generator_nt signature | ✅ PASS |
| 5. No stale imports in unified generators | ❌ FAIL — imports from original |
| 6. OT generator exports complete | ✅ PASS |
| 7. Original not used by server.py | ✅ PASS |
| 8. No circular imports | ✅ PASS |

## Recommended Fix for Claim 5

In `unified_html_generator_nt.py`, replace all 5 occurrences of:
```python
from study_html_generator import _s3_cache_get, _s3_cache_put
from study_html_generator import _s3_cache_get, _s3_cache_put, _strip_md
```
with:
```python
from study_html_generator_nt import _s3_cache_get, _s3_cache_put
from study_html_generator_nt import _s3_cache_get, _s3_cache_put, _strip_md
```

Same fix needed in `unified_html_generator_ot.py` (replace with `study_html_generator_ot`).

Until this fix is applied, **do NOT delete** `study_html_generator.py` — both unified generators depend on it.
