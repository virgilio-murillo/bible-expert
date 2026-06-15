# Investigation Findings: OT Quality & Unified HTML Generator

## Executive Summary

The study.html generator has solid OT support (WLC morph, LXX morph, LXX-ES translation, RTL display) but the JS analysis functions (`explainEnding`, `verbTenseEs`, `contextualMeaning`) silently fail for both Hebrew OSHM codes and LXX dot-notation codes — they only understand Greek RMAC format. The unified_html_generator.py is **completely disconnected** from the codebase (never called) and has **zero OT-specific features**. Additionally, 12 LXX book variants (4,088 verses) are unreachable due to missing aliases in `books.py`.

---

## 1. unified_html_generator.py — Status & Gaps

### Current State: DEAD CODE
- `generate_unified_html` is **not imported or called** from `server.py`, `study_html_generator.py`, or any other module
- Only 1 commit: backup from 2026-06-09
- File: `unified_html_generator.py:65`

### Missing vs study.html for OT:
| Feature | study.html | unified_html |
|---------|-----------|--------------|
| WLC text (RTL, `direction: rtl`) | ✅ line 762, 835-836 | ❌ No RTL CSS or WLC display |
| LXX text line | ✅ line 850-853 | ❌ Only MorphGNT/SBLGNT fallback (line 755-758) |
| LXX-ES translation | ✅ line 854-857 | ❌ Not referenced |
| lxx_morphology hover | ✅ `renderLxxMorph` (line 1097) | ❌ Not implemented |
| Hebrew morph parsing | ❌ (bug, see §4) | ❌ |
| `is_ot` flag | ✅ line 722, 838 | ❌ No OT detection |
| Translation toggle | ✅ `showTranslations()` | ❌ Only RVR button |
| Word study popup | ✅ `openWordStudy()` | ❌ Only hover tooltip |

### What unified DOES have:
- Verse-by-verse expandable sections (exegesis, patristic, TC)
- LLM-generated TC verdicts, patristic themes, exegetical themes
- Manuscript panel with interactive sigla chips
- Cross-references sidebar

---

## 2. study.html JS Template — Bugs with OT Data

### Bug 2a: `renderMorph` for WLC (line 1087-1092)
**How it works:** When `isOT=true` and `D.parallel.WLC[v.v]` exists, the code calls:
```javascript
html += `<div class="verse-line original">${renderMorph(v.v, D.parallel.WLC[v.v])}</div>`;
```
`renderMorph` pulls from `D.morphology[vnum]` — which for OT contains WLC words (since MorphGNT query fails first, then WLC succeeds as primary morphology in `gather_chapter_data` line 85-91).

**The issue:** The rendered `morph-word` spans are fine (they display Hebrew text), but:
- The Hebrew words include morpheme separators (`/`) like `בְּ/רֵאשִׁ֖ית` which display inline
- The verse-line has class `original` → CSS applies `direction: rtl` ✅ correct
- No bug here — display works correctly

### Bug 2b: `showWordTip` tooltip (line 1094-1104)
For WLC words:
- `contextualMeaning(w)` → checks `w.m.startsWith('V-')` → `HVqp3ms` doesn't start with `V-` → returns `''`
- Falls to `w.es` → empty string (WLC has no gloss_es)
- Falls to `w.g` → English gloss from Strong's lexicon (e.g., "create")
- **Result:** Tooltip shows English gloss only. Acceptable but limited.

### Bug 2c: `explainEnding(w)` — FAILS for Hebrew codes (line 911-1084)
For `w.m = "HNcmsa"`:
- None of the startsWith checks match: not `V-`, `CONJ`, `PREP`, `ADV`, `PRT`, `INJ`, `HEB`, `ARAM`, `N-`, `A-`, `T-`
- `firstChar = 'H'` → `pronounTypes['H']` is undefined
- Falls to final generic: `"Forma flexionada de <lemma>"` or empty string

**Impact:** The word study popup shows NO grammatical explanation for Hebrew words. The "📝" breakdown section provides zero useful parsing info.

### Bug 2d: `verbTenseEs(rmac)` — FAILS for Hebrew verbs
For `w.m = "HVqp3ms"`:
- `rmac.startsWith('V-')` → false (it's "HV" not "V-")
- Returns `''`

**Impact:** No tense/voice/mood information displayed for Hebrew verbs.

---

## 3. NT vs OT Feature Gap Comparison

| Feature | NT Chapter | OT Chapter |
|---------|-----------|-----------|
| Word-by-word hover with gloss | ✅ Greek + English/Spanish | ✅ Hebrew + English gloss |
| Grammatical parsing in popup | ✅ Full RMAC explanation | ❌ Generic fallback only |
| Verb tense/voice/mood | ✅ `verbTenseEs` works | ❌ Returns empty |
| Form breakdown (explainEnding) | ✅ Case, gender, number explained | ❌ Returns empty or generic |
| Contextual meaning (participial) | ✅ CONTEXT_MEANINGS lookup | ❌ Returns empty |
| Compound word etymology | ✅ 4233 entries (all Greek) | ❌ No Hebrew compounds |
| Word morphology (prefix/root) | ✅ 575 entries (all Greek) | ❌ No Hebrew word_morphology |
| Exegetical commentaries | ✅ Robertson, Vincent, etc. (27 NT books) | ❌ commentaries table is NT-only |
| Patristic coverage | ✅ 226,426 entries | ✅ 56,863 entries |
| Cross-references | ✅ Full | ✅ Full (e.g., Genesis: 1,952; Psalms: 11,502) |
| Textual apparatus/variants | ✅ 11 major variants | ❌ apparatus table is NT-only |
| External links (BibleHub) | ✅ `/greek/1234.htm` | ❌ BUG: `/greek/H1234.htm` (404) |
| External links (Perseus) | ✅ `&la=greek` | ❌ BUG: still `&la=greek` for Hebrew |
| External links (Logeion) | ✅ Greek-only tool | ❌ BUG: links to Greek Logeion for Hebrew |
| LXX parallel text | N/A for NT | ✅ Displayed with LXX-ES |
| LXX hover/click | N/A | ✅ `renderLxxMorph` + `openLxxStudy` |

---

## 4. `renderMorph` and Hebrew OSHM Codes

### OSHM Format (WLC)
Pattern: `[Language][POS segment(s)]` joined by `/` for compound prefixes

Examples:
| Code | Meaning |
|------|---------|
| `HNcmsa` | Hebrew Noun common masculine singular absolute |
| `HC/Vqw3ms` | Hebrew Conjunction + Verb qal wayyiqtol 3rd masculine singular |
| `HTd/Ncmsa` | Hebrew article-definite + Noun common masculine singular absolute |
| `HVqp3ms` | Hebrew Verb qal perfect 3rd masculine singular |
| `HR` | Hebrew Preposition |
| `HNp` | Hebrew Noun proper (most common: 26,315 occurrences) |

### Why RMAC Functions Fail
The JS functions test for patterns like `V-`, `N-`, `CONJ` etc. Hebrew codes start with `H` (language prefix) followed by POS without a dash. A Hebrew noun is `HNcmsa`, not `N-NSM`.

### Fix Needed
A `explainHebrewMorph(code)` function that:
1. Strips the `H` or `A` (Aramaic) prefix
2. Splits on `/` for compound morphemes
3. Parses each segment: `N`=noun, `V`=verb, `T`=particle, `R`=preposition, `C`=conjunction, `D`=adverb
4. For nouns: `c`/`p`=common/proper, `m`/`f`/`b`=gender, `s`/`p`/`d`=number, `a`/`c`=state
5. For verbs: stem(q/n/p/h/t/D/H/etc), conjugation(p/i/w/j/v/r/c/a), person, gender, number

---

## 5. `openWordStudy` — Hebrew Strong's Links (Bug)

**File:** `study_html_generator.py:1215-1222`

| Link | Hebrew behavior | Expected |
|------|----------------|----------|
| Blue Letter Bible | `lexicon/H1234/kjv/tr/0-1/` | ✅ Works (auto-detects H vs G) |
| BibleHub | `greek/H1234.htm` | ❌ Should be `hebrew/1234.htm` |
| Perseus | `morph?l=אָב&la=greek` | ❌ Should be removed or use `la=hebrew` (not supported) |
| Logeion | `logeion.uchicago.edu/אָב` | ❌ Greek-only. Should be HALOT/BDB link |
| STEP Bible | `strong=H1234` | ✅ Works for Hebrew |

**Fix:** Conditional link generation based on `w.s.startsWith('H')`:
```javascript
const isHeb = w.s && w.s.startsWith('H');
const bibhub = isHeb ? `biblehub.com/hebrew/${w.s.replace('H','')}.htm` 
                     : `biblehub.com/greek/${w.s.replace('G','')}.htm`;
// Remove Perseus/Logeion for Hebrew, add:
// - https://www.sefaria.org/search?q=<lemma>
// - https://www.pealim.com/search/?q=<lemma> (for modern Hebrew roots)
```

---

## 6. LXX Morphology Codes — Dot Notation vs RMAC

### LXX Format
Pattern: `POS.CaseGenderNumber` (dot-separated)

Examples:
| Code | Meaning |
|------|---------|
| `N.NSM` | Noun, Nominative Singular Masculine |
| `V.AAI3S` | Verb, Aorist Active Indicative 3rd Singular |
| `RA.NSM` | Article, Nominative Singular Masculine |
| `C` | Conjunction |
| `P` | Preposition |
| `RP.GS` | Relative Pronoun, Genitive Singular |

### Comparison with RMAC (MorphGNT)
| RMAC | LXX | Difference |
|------|-----|-----------|
| `V-AAI-3S` | `V.AAI3S` | Dash → Dot, dash between mood/person removed |
| `N-NSM` | `N.NSM` | Dash → Dot |
| `CONJ` | `C` | Full word → single letter |
| `PREP` | `P` | Full word → single letter |

### Impact in study.html
`openLxxStudy` (line 1108-1125) is simple — just displays the raw code in a table. No parsing attempted. **Not a bug per se**, but a missing feature: LXX words get no grammatical explanation while NT Greek words get full explanations.

### Fix
Since LXX codes are structurally similar to RMAC (same grammatical categories, just different syntax), a normalizer could convert `N.NSM` → `N-NSM` before passing to `explainEnding`, or a parallel `explainLxxMorph` could handle the dot-notation directly.

---

## 7. `gather_chapter_data` — Book Name `candidates` Handling

### How It Works (study_html_generator.py:39-312)
1. `candidates = get_all_db_names(resolved)` returns `[canonical_name, alias1, alias2, ...]`
2. Each DB query loops: `for b in candidates:` and breaks on first match

### Book Name Mapping Issue
The DB uses different naming conventions per table:
| Table | OT Book Names | Example |
|-------|---------------|---------|
| `verses` (WLC) | Abbreviated | `Gen`, `Ps`, `1Sam` |
| `morphology` (WLC) | Abbreviated | `Gen`, `Ps`, `1Sam` |
| `morphology` (LXX) | Abbreviated + variants | `Gen`, `JoshA`, `JoshB`, `DanOG` |
| `verses` (LXX) | Abbreviated + variants | Same as above |
| `patristic` | Full canonical | `Genesis`, `Psalms`, `1 Samuel` |
| `cross_refs` | Full canonical | `Genesis`, `Psalms` |
| `commentaries` | Full canonical (NT only) | `Matthew`, `John` |
| `apparatus` | Full canonical (NT only) | `Matthew`, `John` |

### ✅ What Works
- `books.py` aliases include abbreviated forms (e.g., `"Gen"` for Genesis, `"Ps"` for Psalms)
- The loop finds `"Genesis"` for patristic, then `"Gen"` for morphology/verses → correct

### ❌ What's Broken: 12 LXX Books Unreachable
These LXX variant names are NOT in `books.py` aliases:
- `JoshA`, `JoshB` (Joshua A/B text traditions)
- `JudgA`, `JudgB` (Judges A/B text traditions)
- `DanOG`, `DanTh` (Daniel Old Greek / Theodotion)
- `BelOG`, `BelTh` (Bel & the Dragon)
- `SusOG`, `SusTh` (Susanna)
- `1Esdr`, `2Esdr` (Esdras)

**Result:** 4,088 LXX verses + all their morphology data are completely inaccessible via any tool.

**Fix:** Add these as aliases in `books.py`:
```python
6: ("Joshua", ["Josh", "Jos", ..., "JoshA", "JoshB"]),
7: ("Judges", ["Judg", ..., "JudgA", "JudgB"]),
27: ("Daniel", ["Dan", ..., "DanOG", "DanTh"]),
```

---

## 8. DB Integrity: WLC Morphology vs Verses Word Count

**Result: PERFECT MATCH** — All 39 OT books have exactly matching word counts between `morphology` (version='WLC') and `verses` (version='WLC'). No discrepancies found.

Verified via SQL query comparing `COUNT(*)` from morphology vs `SUM(word_count_estimate)` from verses text. Zero rows with difference > 0.

---

## 9. `exegetical` Field and `greek_commentaries` for OT

### `commentaries` Table: NT-ONLY
Contains 27 NT books (Matthew through Revelation). Sources: Robertson's Word Pictures, Vincent's Word Studies, etc.

**OT impact:**
- `data["greek_commentaries"]` = empty dict for all OT chapters
- The "📖 exégesis" button (line 875) never appears for OT chapters (`commCount = 0`)
- The unified_html's exegesis section has nothing to show for OT

### `exegetical` Field
Set to `""` unconditionally (line 306). It's a placeholder — the actual exegetical content comes from `greek_commentaries` dict which is NT-only.

### Gap
OT chapters get **no scholarly commentary** from Robertson, Vincent, etc. This is a significant content gap.

---

## 10. Recommendations for OT Parity

### Priority 1 — Critical Bugs (Functional Breakage)
1. **Add LXX variant aliases to books.py** — JoshA/B, JudgA/B, DanOG/Th, BelOG/Th, SusOG/Th, 1Esdr, 2Esdr
2. **Fix external links for Hebrew** — BibleHub `/hebrew/` path, remove Perseus/Logeion for Hebrew, add Sefaria

### Priority 2 — Morph Parsing (Usability)
3. **Add `explainHebrewMorph(code)` JS function** — Parse OSHM codes to human-readable Spanish explanations
4. **Add `explainLxxMorph(code)` or normalize LXX codes** — Either convert `N.NSM` → `N-NSM` for reuse of explainEnding, or write parallel function
5. **Add `hebrewVerbTenseEs(code)` function** — Parse Hebrew verb stems (qal, niphal, piel, hiphil, etc.) with Spanish explanations

### Priority 3 — Content Gaps
6. **Ingest OT commentaries** — Sources: Keil & Delitzsch (public domain), Lange's Commentary, Pulpit Commentary
7. **Add Hebrew compound/etymology data** — Hebrew root system (3-letter שרשים) is central to understanding; needs a `hebrew_roots` table
8. **Add Hebrew OSHM description table** — Like `rmac_codes` but for OSHM format, mapping codes to descriptions

### Priority 4 — Unified HTML Integration
9. **Connect unified_html_generator to server.py** — Currently dead code; needs to be called from `chapter_study` or a new MCP tool
10. **Add OT awareness to unified_html** — RTL display, LXX line, LXX-ES translation, `is_ot` detection
11. **Add LXX morphology to unified_html** — Render clickable LXX words with hover, like study.html does

### Priority 5 — Nice-to-have
12. **Hebrew word study popup** — Show root analysis (3-letter root), binyan (verb pattern), and related words from same root
13. **OT apparatus/critical apparatus** — Dead Sea Scrolls variants vs MT (would need significant data ingestion)
14. **Interlinear mode for WLC** — Word-for-word alignment between Hebrew and English/Spanish

---

## File References

| File | Line(s) | Issue |
|------|---------|-------|
| `study_html_generator.py` | 85-91 | WLC loads as primary morphology when MorphGNT absent |
| `study_html_generator.py` | 166-180 | LXX morphology loaded separately |
| `study_html_generator.py` | 835-836 | `renderMorph(v.v, D.parallel.WLC[v.v])` for OT |
| `study_html_generator.py` | 887-900 | `verbTenseEs` — RMAC-only |
| `study_html_generator.py` | 911-1084 | `explainEnding` — RMAC-only, Hebrew falls through |
| `study_html_generator.py` | 1087-1092 | `renderMorph` function |
| `study_html_generator.py` | 1094-1104 | `showWordTip` — gloss-only for Hebrew |
| `study_html_generator.py` | 1215-1222 | External links — Greek-biased URLs |
| `unified_html_generator.py` | 65 | `generate_unified_html` — never called |
| `unified_html_generator.py` | 748-758 | JS only renders `D.morphology` as Greek |
| `books.py` | 6-7, 27 | Missing JoshA/B, JudgA/B, DanOG/Th aliases |
| DB: `commentaries` | — | NT-only (27 books) |
| DB: `apparatus` | — | NT-only (27 books) |
| DB: `compounds` | — | Greek-only (4,233 entries) |
| DB: `word_morphology` | — | Greek-only (575 entries) |
