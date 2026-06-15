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

**FINAL STATEMENT:** Both `unified_html_generator_nt.py` and `unified_html_generator_ot.py` have 5 stale import sites each (10 total) that reference `study_html_generator` instead of their respective split files. This is a MEDIUM-severity maintenance debt. The system functions correctly today. The fix is a mechanical find-and-replace (`sed -i 's/from study_html_generator import/from study_html_generator_nt import/' unified_html_generator_nt.py` and equivalent for OT). No behavioral change will result because the imported functions are byte-identical across all three source files.

---

## RULING ON DISPUTE 4: Deuterocanonical Routing

**CLAIM (Pair 1 — Contrarian R2):** Routing deuterocanonical books (IDs 67+) to the NT generator is a design gap because those books are primarily LXX texts and the OT generator now has `_translate_lxx()` which they would benefit from.

**CLAIM (Pair 2 — Investigator R2):** This is NOT a bug or regression — deuterocanonicals never had `_translate_lxx` before the split. The NT generator still queries LXX text. It's a future enhancement opportunity.

**VERDICT: UPHELD (investigator) — enhancement, not bug**

**REASONING:** Judge confirmed:
- `grep _translate_lxx study_html_generator.py` → 0 matches. The original never had this function.
- `_translate_lxx` exists only in `study_html_generator_ot.py` (lines 190, 378) — it's a NEW capability added during the split.
- Deuterocanonicals get the exact same code path they always had (the NT generator IS the unmodified original).
- No regression exists. The split did not remove any capability from deuterocanonical processing.

**FINAL STATEMENT:** Deuterocanonical books (IDs 67+) routing to the NT generator is not a bug — it's the pre-existing behavior preserved unchanged. The `_translate_lxx()` function is a new OT-only enhancement. A future enhancement could add a third routing category for deuterocanonicals, or expand `_OT_NAMES` to include LXX-primary books. Priority: LOW (enhancement request, zero regression).

---

## RULING ON DISPUTE 5: "Runtime Test" Methodology Claim

**CLAIM (Pair 0 — Contrarian R1):** The investigator claimed "confirmed via runtime test" but may have only performed source inspection.

**CLAIM (Pair 0 — Investigator R2):** Concedes that "confirmed by source inspection" would have been more accurate for some verifications, but conclusions are unaffected.

**VERDICT: UPHELD (contrarian's challenge was valid; investigator appropriately conceded)**

**REASONING:** The distinction between "runtime test" and "static analysis" matters for methodology rigor. The investigator's conclusions were correct regardless of method, but overstating the verification approach is a credibility issue in formal investigations. The concession was appropriate.

**FINAL STATEMENT:** Import integrity was verified by both static analysis (grep/AST) and selective runtime testing. All 6 imported names resolve correctly. The methodology distinction does not affect the correctness of any finding.

---

## RULING ON DISPUTE 6: Import Fix Complexity ("Trivial" vs "Non-Trivial")

**CLAIM (Pair 2 — Contrarian):** The fix requires "careful mapping across 10 import sites" and is non-trivial because a wrong import could create cross-generator dependencies.

**CLAIM (Pair 2 — Investigator):** The fix is trivial because all three implementations are byte-identical — importing from the "wrong" file produces identical behavior.

**VERDICT: UPHELD (investigator) — the fix IS trivial**

**REASONING:** Because `_s3_cache_get`, `_s3_cache_put`, and `_strip_md` are byte-identical across all three source files (independently verified by Pair 0), there is zero "correctness of mapping" risk. Even an accidental cross-import produces correct behavior. The fix is a mechanical `sed` operation.

**FINAL STATEMENT:** The stale import fix is trivial: two `sed` commands, one per unified file. No mapping risk exists because the target functions are byte-identical regardless of source file. The only value of the fix is module hygiene — allowing future deletion of the original `study_html_generator.py`.

---

## SUMMARY OF FINAL FINDINGS

| # | Finding | Severity | Action Needed |
|---|---------|----------|---------------|
| 1 | SyntaxWarning in OT generator (lines with `\.` in JS regex inside f-strings) | LOW | Fix: use raw strings or `\\\\.` |
| 2 | 10 stale imports in unified generators pointing to original instead of split files | MEDIUM | Fix: mechanical sed replacement |
| 3 | Original `study_html_generator.py` and `unified_html_generator.py` are dead code | LOW | Can be deleted after fixing #2 |
| 4 | Deuterocanonicals route to NT generator, missing new `_translate_lxx()` | LOW | Future enhancement, not regression |
| 5 | All imports, signatures, and routing work correctly — no functional bugs | ✅ | No action needed |

**Overall verdict:** The OT/NT generator split is **functionally correct**. The NT path works identically to the pre-split behavior. The only actionable items are maintenance hygiene (stale imports, dead code, escape sequence warnings) — none affect runtime correctness.
