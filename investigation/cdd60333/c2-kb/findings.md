# OT Quality & Unified HTML Generator — Investigation Findings

## Executive Summary

The study.html generator has good OT support (WLC + LXX rendering, RTL, hover tooltips), but several JS functions that parse morphology codes are broken for both Hebrew (OSHM format) and LXX (dot-separated format). The unified_html_generator has **zero** OT-specific handling. Additionally, the commentaries and apparatus databases have no OT entries, leaving major sections empty for OT chapters.

---

## 1. unified_html_generator.py — Missing OT Features

**File**: `unified_html_generator.py`

### What it does for OT today:
- Renders `D.morphology` (which will be WLC Hebrew words) into a div with class `greek-line` (line 753-764)
- Shows basic hover tooltip: `w.es || w.g` + lemma (line 770-776)
- No word study popup (no `onclick` handler on morph-words)

### What's MISSING vs study.html:

| Feature | study.html | unified_html |
|---------|-----------|--------------|
| WLC Hebrew line (RTL, correct font) | ✅ `.verse-line.original` | ❌ Uses `.greek-line` (LTR, green, wrong font) |
| LXX Greek line | ✅ via `renderLxxMorph()` | ❌ Not rendered |
| LXX-ES Spanish translation | ✅ via `D.lxx_spanish` | ❌ Not rendered |
| Word study popup on click | ✅ `openWordStudy()` | ❌ No onclick handler |
| Compound etymology | ✅ `D.compounds` | ❌ Not used |
| Verb tense explanation | ✅ `verbTenseEs()` | ❌ Not called |
| Form breakdown (explainEnding) | ✅ | ❌ Not called |
| External links (BLB, BibleHub) | ✅ | ❌ Not rendered |
| Translations modal | ✅ `showTranslations()` | ❌ Not available |

### RTL Bug (line 649 CSS + line 753-764 JS):
```css
/* Current - unified_html_generator.py line 649 */
.greek-line { font-family: 'Noto Serif', Georgia, serif; color: #1b5e20; }
```
Hebrew words from WLC get rendered LTR in green. Should be RTL with SBL Hebrew font.

---

## 2. study.html JS — Morphology Code Parsing Bugs

### 2a. WLC Hebrew codes (OSHM format) — COMPLETELY BROKEN

**Format example**: `HVqp3ms` (H=Hebrew, V=Verb, q=Qal, p=Perfect, 3=Person, m=masc, s=sing)  
**Also with separators**: `HR/Ncfsa`, `HTd/Ncmpa`, `HC/To`

**Affected functions** (study_html_generator.py lines 870-1080):

| Function | Check | WLC code | Result |
|----------|-------|----------|--------|
| `verbTenseEs()` (line 870) | `rmac.startsWith('V-')` | `HVqp3ms` | **FALSE** — no output |
| `contextualMeaning()` (line 955) | `w.m.startsWith('V-')` | `HVqp3ms` | **FALSE** — no output |
| `explainEnding()` (line 967) | Checks RMAC patterns | `HVqp3ms` | Falls to generic fallback |
| `explainEnding()` nouns | `rmac.startsWith('N-')` | `HNcmsa` | **FALSE** — no case explanation |
| `explainEnding()` articles | `rmac.startsWith('T-')` | `HTd/Ncmpa` | **FALSE** |

**Impact**: Hebrew words in study.html get NO morphological explanation. The hover tooltip falls back to lexicon gloss (which works), but the word study popup shows only "Forma flexionada de {lemma}" — no verb conjugation details, no noun case explanation.

### 2b. LXX Greek codes (dot-separated) — NEARLY COMPATIBLE

**Format example**: `V.AAI3S`, `N.NSM`, `RA.NSM`

| Function | Check | LXX code | Result |
|----------|-------|----------|--------|
| `verbTenseEs()` | `rmac.startsWith('V-')` | `V.AAI3S` | **FALSE** — no output |
| `explainEnding()` | `rmac.startsWith('V-')` | `V.AAI3S` | **FALSE** |
| `explainEnding()` | `rmac.startsWith('N-')` | `N.NSM` | **FALSE** |

**Fix opportunity**: A simple normalization `m.replace('.', '-')` would make LXX codes parse correctly for:
- Verb tense/voice/mood (positions 0-2 after separator identical to RMAC)
- Non-participle verb person/number (LXX "3S" = no dash, actually works BETTER than RMAC "−3S")
- Noun case/gender/number (identical structure)

### 2c. EXISTING BUG: MorphGNT RMAC person/number parsing

**File**: study_html_generator.py, `explainEnding()` function (line ~1040-1080)

For `V-AAI-3S`: `rmac.substring(2)` = `"AAI-3S"`, then:
```javascript
const p = code[off+3];  // = '-' (the dash separator!)
const n = code[off+4];  // = '3' 
```
- `persons['-']` → undefined, shows literal '-'
- `numbers['3']` → undefined, shows literal '3'

The code was written assuming no dash between TVM and person (like `V-AAI3S`), but MorphGNT stores `V-AAI-3S` (with dash).

**Severity**: The tense/voice/mood extraction works fine (lines 0-2). Only person/number display is broken. `verbTenseEs()` tooltip is unaffected since it only shows T/V/M.

---

## 3. openWordStudy — Hebrew External Links (lines 1190-1210)

**Broken links for H-numbered Strong's**:

```javascript
// Line ~1208 - BibleHub
`https://biblehub.com/greek/${(w.s||'').replace('G','')}.htm`
// For H7225 → "biblehub.com/greek/H7225.htm" — WRONG
// Should be: "biblehub.com/hebrew/7225.htm" 
```

```javascript
// Line ~1210 - Perseus
`https://www.perseus.tufts.edu/hopper/morph?l=${encodeURIComponent(w.l)}&la=greek`
// For Hebrew word → uses la=greek — WRONG (should check if H-number)
```

```javascript
// Line ~1211 - Logeion
`https://logeion.uchicago.edu/${encodeURIComponent(w.l)}`
// Logeion doesn't support Hebrew — should be omitted or replaced
```

**Correct links for Hebrew would be**:
- BibleHub: `https://biblehub.com/hebrew/${num}.htm` (strip 'H' prefix)
- Blue Letter Bible: works with H numbers (already correct)
- STEP Bible: works with H numbers (already correct)
- Replace Perseus/Logeion with: Sefaria, HALOT, or BDB references

---

## 4. openLxxStudy — Minimal Implementation (lines 1130-1145)

The `openLxxStudy()` popup shows:
- Word, lemma, Strong's, morphology code, gloss — ✅ basic info
- NO form breakdown (explainEnding not called)
- NO compound etymology
- NO verb tense explanation
- NO external links

This is significantly less informative than `openWordStudy()` for MorphGNT words.

---

## 5. gather_chapter_data — Candidate Handling (lines 39-312)

**Book name variants work correctly**: `get_all_db_names("Genesis")` returns `["Genesis", "Gen", "Gn", ...]`. The code iterates through candidates for each query, finding "Gen" which matches the DB.

**Commentaries query uses `book` directly** (line 300):
```python
comm_rows = db.execute("...FROM commentaries WHERE book=? AND chapter=?", (book, chapter))
```
Uses the resolved canonical name ("Genesis") without trying candidates. Since commentaries table uses canonical long names ("Matthew"), this works for NT. Would need candidate iteration if OT commentaries were added under short names.

---

## 6. Database Coverage Gaps

### Commentaries table — NT ONLY
```
NT entries: 33,050 (27 books)
OT entries: 0
```
Sources: Robertson's Word Pictures, Alford's, Bengel's, Expositor's, Meyer's, Vincent's — all NT-focused commentaries.

**Impact**: `greek_commentaries` dict is always empty for OT → exegesis section never renders. The `showExegetical()` button never appears for OT verses.

### Apparatus table — NT ONLY
```
NT entries: 4,284
OT entries: 0
```
**Impact**: TC (Textual Criticism) section never renders for OT.

### Patristic table — Mostly NT
```
NT entries: 278,252
OT entries: 5,037 (only 15 books)
```
Most OT patristic data is in Job (4,287). Major books like **Genesis, Exodus, Psalms, Isaiah** have **zero** patristic entries.

### Cross-references — Sparse OT
```
NT cross-refs: 63,180
OT cross-refs: 1,692
```
OT coverage is ~2.7% of NT coverage.

---

## 7. Word Count Integrity — ✅ VERIFIED OK

```sql
-- No mismatches found between WLC morphology and WLC verses word counts
SELECT ... HAVING morph_verse_count != verse_count → 0 rows
```
All 39 OT books have identical verse counts in both the morphology and verses tables. Word-level counts also match (verified for Genesis 1 — all 31 verses match exactly).

---

## 8. LXX-ES Translation Integration

**In study.html** (working): Lines 849-853 render LXX Spanish translation when `D.lxx_spanish[v.v]` exists:
```javascript
if (D.lxx_spanish && D.lxx_spanish[v.v]) {
  html += `<div class="verse-line" style="color:#6a1b9a;font-style:italic">
    <span class="vlabel">LXX-ES</span>${D.lxx_spanish[v.v]}</div>`;
}
```

**In unified_html**: Not present at all. The `chapter_data` contains `lxx_spanish` but the unified template never reads or renders it.

---

## 9. Summary: NT vs OT Feature Matrix

| Feature | NT (study.html) | OT (study.html) | Unified (any) |
|---------|:-:|:-:|:-:|
| Original text display | ✅ Greek LTR | ✅ Hebrew RTL | ⚠️ Wrong direction for Hebrew |
| Word-level morphology hover | ✅ Full | ⚠️ Gloss only (no parsing) | ⚠️ Basic gloss only |
| Word study popup | ✅ Full | ⚠️ No verb/noun explanation | ❌ None |
| External links | ✅ BLB/BibleHub/Perseus/Logeion | ❌ Broken URLs | ❌ None |
| LXX parallel | N/A | ✅ Displayed | ❌ Missing |
| LXX-ES translation | N/A | ✅ Displayed | ❌ Missing |
| Commentaries/Exegesis | ✅ 6 sources | ❌ 0 sources in DB | ❌ 0 sources |
| Apparatus/TC | ✅ 4,284 entries | ❌ 0 entries in DB | ❌ 0 entries |
| Patristic | ✅ 278K entries | ⚠️ 5K entries (15 books) | ⚠️ Same data |
| Cross-references | ✅ 63K | ⚠️ 1.7K | ⚠️ Same data |
| Compound etymology | ✅ | ❌ (not applicable) | ❌ Not rendered |
| Verb tense/voice tooltip | ✅ | ❌ OSHM not parsed | ❌ Not called |
| Form breakdown | ⚠️ Person/number bug | ❌ OSHM not parsed | ❌ Not called |

---

## 10. Recommended Improvements (Priority Order)

### P0 — Bugs to Fix
1. **explainEnding() dash handling** (study_html_generator.py ~line 1040): Skip the '-' separator before person/number: `const pIdx = code[off+3]==='-' ? off+4 : off+3;`
2. **Hebrew external links** (line ~1208-1211): Detect H-numbers → use `/hebrew/` path on BibleHub, remove Perseus/Logeion for Hebrew
3. **Unified HTML RTL** (unified_html_generator.py line 649/753): Detect OT → add `direction:rtl` and Hebrew font to the text line

### P1 — OT Morphology Parsing
4. **Add Hebrew OSHM parser**: New function `explainHebrewMorph(code)` that understands H+POS+stem+tense+person+gender+number format. Map Hebrew stems (q=Qal, n=Niphal, p=Piel, etc.) and tenses (p=Perfect, i=Imperfect, etc.) to Spanish explanations.
5. **LXX code normalization**: Before passing to explainEnding, normalize: `code.replace('.', '-')`. This makes LXX codes work with existing RMAC parser.

### P2 — Unified HTML Parity
6. **Add OT text lines**: Render WLC (RTL), LXX, and LXX-ES in the verse block
7. **Add word study popup**: Port `openWordStudy`/`openLxxStudy` to unified template
8. **Add translations button**: Port `showTranslations()` to unified

### P3 — Data Gaps
9. **OT commentaries**: Ingest Keil & Delitzsch (public domain), Matthew Henry, or other OT commentary sources into the commentaries table
10. **OT apparatus**: Add BHS critical apparatus data (Masorah, Qere/Ketiv variants, Dead Sea Scrolls variants)
11. **OT patristic expansion**: ANF/NPNF have extensive OT commentary (Origen on Genesis, Jerome on Isaiah, Augustine on Psalms) — needs better verse-level indexing
12. **OT cross-references**: Treasury of Scripture Knowledge has extensive OT cross-refs — ingest full dataset
