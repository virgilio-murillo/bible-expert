# Rebuttal — Round 1

## Challenge 1: Deuterocanonical Routing Gap

**CONCEDE (partially).**

The contrarian is correct that deuterocanonical books (IDs 67+: Tobit, Judith, Wisdom, Sirach, Baruch, 1-2 Maccabees) route to the NT generator because `_OT_NAMES` only covers IDs 1–39. And the OT generator's `_translate_lxx()` at line 190 does provide LXX-to-Spanish translation that these books would benefit from.

However, I refine the severity assessment:

1. **The NT generator still fetches LXX data.** `study_html_generator_nt.py` lines 63–66 query `LXX` text and store it in `data["parallel"]["LXX"]`. The raw LXX Greek is still displayed to the user. What's missing is only the `_translate_lxx()` Spanish translation layer — not the LXX text itself.

2. **The NT generator fetches WLC/Hebrew morphology as fallback** (line 85–91), so even Hebrew-text deuterocanonical fragments wouldn't be lost.

3. **This is a known design scope boundary, not an oversight.** The split was explicitly scoped to the 66 Protestant canon (IDs 1–66). Deuterocanonical routing is a future enhancement, not a regression from the split — these books routed to the *same original generator* before the split. The `_translate_lxx()` function was added as part of the OT generator improvements, so deuterocanonicals never had it before.

**Net verdict:** Correct observation. Severity is "enhancement opportunity" rather than "functional gap introduced by the split." Conceded as understated in original findings.

---

## Challenge 2: Hot-Path Dependency on Original

**REBUT.**

The contrarian states: "The import from the original isn't a corner case — it's invoked on every `generate_unified_html` call."

This is factually accurate but the risk characterization is overstated:

1. **`generate_unified_html` is a background-thread operation, not the hot path.** Looking at `server.py` lines 932–937, `generate_unified_html` is called inside `_generate_background_analyses()` which runs in a `threading.Thread`. The user-facing hot path is `generate_study_html` (line 922), which returns immediately and opens the browser. The unified analysis generates asynchronously afterward.

2. **The original file's deletion is prevented by obvious grep evidence.** Running `grep -r "from study_html_generator import"` shows 15 matches across 3 files. Anyone attempting to delete the original would immediately discover these imports. This isn't a "fragile coupling that might surprise someone" — it's 15 explicit import statements.

3. **The lazy import pattern is intentional.** These are inside function bodies (line 67 of `generate_unified_html`), not module-level. This is a deliberate design choice: the unified generators are heavyweight (LLM calls, S3 caching) and only run when explicitly triggered. Lazy imports prevent loading unused dependencies at server startup.

4. **The functions imported (`_s3_cache_get`, `_s3_cache_put`) exist in both `study_html_generator_nt.py` (lines 9, 21) and `study_html_generator_ot.py` (lines 9, 21).** The recommended fix (import from the split files instead) is trivial and acknowledged in our findings. The risk of breakage is real but the blast radius is limited to background unified analysis, not the primary study generation.

**Net verdict:** The characterization as "hot path" is incorrect — it's a background thread. The dependency is real but the risk is bounded and the fix is trivial.

---

## Challenge 3: Incomplete Split / Carbon Copy Evidence

**CONCEDE (fully).**

The contrarian is correct on all points:

1. `unified_html_generator.py` (unsuffixed original) exists on disk alongside the `_nt` and `_ot` suffixed copies.
2. All three files have identical imports at identical line numbers (67, 143, 191, 208, 251).
3. This confirms the split was a copy operation where `unified_html_generator_nt.py` and `unified_html_generator_ot.py` were copied from the original without updating their internal `from study_html_generator import ...` lines to point to their respective split study generators.

The contrarian's characterization — "the split appears incomplete" — is accurate for the unified generators. The study generators (`study_html_generator_nt.py` / `_ot.py`) were properly differentiated (NT has no `_translate_lxx`, OT has it at line 378; OT has compound word decomposition, different line counts). But the unified generators are indeed unmodified copies.

The recommended fix from our findings remains correct: update imports in `unified_html_generator_nt.py` to use `from study_html_generator_nt import ...` and similarly for OT. Then the unsuffixed original can be safely removed.

**Net verdict:** Fully conceded. The findings identified the problem correctly but understated the "why" — it's not just lingering imports but an incomplete copy-and-update operation.

---

## Summary

| Challenge | Verdict |
|-----------|---------|
| C1: Deuterocanonical routing gap | **PARTIALLY CONCEDE** — correct observation, but severity is "new enhancement never existed before" not "regression from split" |
| C2: Hot-path dependency | **REBUT** — it's a background thread, not the hot path; risk is bounded |
| C3: Incomplete split evidence | **FULLY CONCEDE** — the unified generators are unmodified copies |
