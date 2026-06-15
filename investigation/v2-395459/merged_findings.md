## internal-investigator (Pair 0: MANDATORY FIRST: Query the customer's CloudWatch metrics (TT)
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


## docs-investigator (Pair 1: Investigate using AWS official documentation. Find relevant )
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
3. `gather_chapter_data` runs, gathers verse

## bug-repro-agent (Pair 2: Reproduce the issue. Write a minimal reproduction that MATCH)
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

The original `study_html_generator.py` serves as a **shared utility library** for 

## Judge Rulings
# Judge Rulings — Investigation v2-395459

**Subject:** NT chapter_study functionality after OT/NT generator split  
**Date:** 2026-06-14T22:13 CST  
**Judge verification method:** Independent `wc -l`, `grep`, and runtime tests on current HEAD

---

## DATA COMPLETENESS CHECK

This investigation concerns a **local code refactoring** (splitting study_html_generator into OT/NT variants), NOT an AWS customer support case. The Investigation Checklist (CloudWatch metrics, fleet-wide baselines, service events) does not apply. The relevant verification criteria are:

- ✅ Runtime import testing performed
- ✅ File line counts independently verified by judge
- ✅ Import chains verified by grep
- ✅ SyntaxWarning reproduced after __pycache__ clearing

No gaps.

---

## RULING ON DISPUTE 1: SyntaxWarning Line Number Mechanism

**CLAIM (Pair 0 — Investigator):** The SyntaxWarning at lines 1611/1615 is real and reproducible. The `__pycache__` explanation for why the contrarian initially failed to reproduce is correct. Original R1 attributed it to "byte offsets" — corrected in R2 to "CPython f-string line tracking bug."

**CLAIM (Pair 0 — Contrarian):** The mechanism is NOT byte offsets but a CPython PEP 701 bug in f-string AST line number tracking. Core facts (warning exists, __pycache__ suppresses it) are correct.

**VERDICT: UPHELD (investigator)**

**REASONING:** Judge independently confirmed:
- `rm __pycache__/study_html_generator_ot.cpython-*.pyc && python3 -Wall -c "import study_html_generator_ot"` → warnings at lines 1611, 1615
- File has only 1606 lines → confirms CPython misreports line numbers in multi-line f-strings
- Mechanism correction (byte offset → CPython f-string bug) was appropriately conceded in R2

**FINAL STATEMENT:** The SyntaxWarning is real, reproducible, and cosmetic. It fires at reported lines 1611/1615 which exceed the file's 1606 actual lines due to a CPython f-string line tracking bug (PEP 701, Python 3.12+). Clearing `__pycache__` is required to observe it. The escape sequences `\.` exist at physical lines containing JavaScript regex patterns inside Python f-strings. This is a minor code quality issue, not a runtime bug.

---

## RULING ON DISPUTE 2: File Line Counts

**CLAIM (Pair 0 — Investigator R2):** Line counts are 1392, 1392, 1606, 893, 893, 1044.

**CLAIM (Pair 1 — Contrarian R2):** Line counts are 1268, 1268, 1469, 801, 801, 942. Called investigator's numbers "fabricated or stale."

**VERDICT: UPHELD (investigator) — Contrarian's numbers are wrong.**

**REASONING:** Judge independently ran `wc -l` on all six files at current HEAD:

| File | Investigator claimed | Contrarian claimed | Judge verified |
|------|---------------------|-------------------|---------------|
| `study_html_generator.py` | 1392 | 1268 | **1392** ✅ |
| `study_html_generator_nt.py` | 1392 | 1268 | **1392** ✅ |
| `study_html_generator_ot.py` | 1606 | 1469 | **1606** ✅ |
| `unified_html_generator.py` | 893 | 801 | **893** ✅ |
| `unified_html_generator_nt.py` | 893 | 801 | **893** ✅ |
| `unified_html_generator_ot.py` | 1044 | 942 | **1044** ✅ |

The contrarian's accusation of "fabricated numbers" was itself factually incorrect. The investigator's line counts are exact.

**FINAL STATEMENT:** The file line counts at current HEAD are: original=1392, NT=1392, OT=1606, unified_original=893, unified_NT=893, unified_OT=1044. NT files are byte-for-byte copies of the originals. OT files are 214/151 lines longer due to `_translate_lxx()` and related LXX enhancements.

---

## RULING ON DISPUTE 3: Stale Imports Severity (CRITICAL vs MEDIUM)

**CLAIM (Pair 1 — Investigator):** `unified_html_generator_nt.py` and `unified_html_generator_ot.py` importing from the original `study_html_generator.py` is a "CRITICAL BUG."

**CLAIM (Pair 0 & 2 — Investigators/Contrarians):** Severity should be MEDIUM — the system works today, the risk is latent, and the imported functions are byte-identical across all three files.

**VERDICT: PARTIALLY UPHELD (downgrade to MEDIUM)**

**REASONING:** Judge confirmed:
1. 10 stale import sites exist (5 per unified file) — verified by grep
2. The system works today because `study_html_generator.py` still exists
3. The imported functions (`_s3_cache_get`, `_s3_cache_put`, `_strip_md`) are identical in all three source files — verified by Pair 0's investigation
4. No behavioral difference would result from importing from the "wrong" split file
5. The original `unified_html_generator.py` is dead code (zero importers) — verified by grep returning empty

"CRITICAL" requires immediate breakage or data loss. This is a latent maintenance risk — if someone deletes the original file during cleanup, 10 import sites break. The fix is a mechanical sed substitution. Severity: **MEDIUM (latent, not active).**

**FINAL STATEMENT:** Both `unified_html_generator_nt.py` and `unified_html_generator_ot.py` have 5 stale import sites each (10 total) that reference `study_html_generator` instead of their respective split files. Th