# Early Recommendations — Bible Expert OT Quality Investigation
*Generated: 11:45 by Head Agent | Confidence: HIGH (4+ sources)*

## EXECUTIVE SUMMARY

The bible-expert project has solid OT data (WLC + LXX morphology fully ingested, 929 chapters each) but contains **3 critical JS bugs** and **1 major structural gap** that prevent OT morphology from being useful to users. The unified_html_generator.py has zero OT awareness and needs significant additions.

---

## CRITICAL BUGS (Fix Immediately)

### BUG-1: Hebrew OSHM morphology codes not parsed in JS
**File**: `study_html_generator.py`, lines 966–1083 (explainEnding), 887–896 (verbTenseEs)  
**Problem**: `explainEnding()` and `verbTenseEs()` check for RMAC format (`V-AAI-3S`) only. Hebrew WLC codes are OSHM format (`HVqp3ms`, `HNcmsa`). All Hebrew words fall to generic fallback "Forma flexionada de X".  
**Fix**: Add an OSHM parser function before the RMAC branches in `explainEnding`:
```javascript
// At start of explainEnding(), after setting rmac:
if (rmac && rmac[0] === 'H') return explainHebrewMorph(rmac, form, lemma);
if (rmac && rmac[0] === 'A') return explainHebrewMorph(rmac, form, lemma);
```
Then implement `explainHebrewMorph()` using OSHM spec:
- `H[N|A|P...]` = part of speech  
- Verbs: `HV[stem][conj][pers][gender][num]` where stem=q(al)/N(iphal)/p(iel)/P(ual)/h(ithpael)/hi(phil)/H(ophal)  
- Nouns: `HN[type][gender][number][state]` where state=a(bsolute)/c(onstruct)/d(determined)  
Reference: https://hb.openscriptures.org/parsing/HebrewMorphologyCodes.html

### BUG-2: LXX morphology codes use dot-format (V.AAI3S) not RMAC dash-format (V-AAI-3S)
**File**: `study_html_generator.py`, lines 887 (verbTenseEs), 966 (explainEnding)  
**Problem**: LXX codes use dots (CATSS format). All RMAC checks use dashes. Zero LXX words get morphological explanation.  
**Fix** (1 line): Normalize at the top of `explainEnding` and `verbTenseEs`:
```javascript
function verbTenseEs(rmac) {
  const code = (rmac || '').replace(/\./g, '-');  // CATSS → RMAC normalization
  if (!code.startsWith('V-')) return '';
  // ... rest unchanged, but use `code` instead of `rmac`
```
**Note**: LXX codes also lack the hyphen between tense+voice+mood and person+number (`V-AAI3S` vs `V-AAI-3S`). May need to insert hyphen at position offset+3.

### BUG-3: openFullStudy Hebrew external links point to Greek-only resources
**File**: `study_html_generator.py`, lines 1215–1225  
**Problem**: All 4 external links use Greek paths: `biblehub.com/greek/`, Perseus `la=greek`, Logeion (LSJ Greek only). For Hebrew words (Strong's H-prefix), all links are wrong.  
**Fix**: Detect Hebrew by Strong's number prefix:
```javascript
const isHeb = (w.s || '').startsWith('H');
const hNum = isHeb ? (w.s || '').replace('H', '') : '';
const gNum = isHeb ? '' : (w.s || '').replace('G', '');
// Hebrew links:
if (isHeb) html += `
  <li><a href="https://www.blueletterbible.org/lexicon/h${hNum}/kjv/wlc/0-1/" target="_blank">Blue Letter Bible — Hebreo</a></li>
  <li><a href="https://biblehub.com/hebrew/${hNum}.htm" target="_blank">BibleHub — Concordancia</a></li>
  <li><a href="https://www.stepbible.org/?q=strong=${w.s || ''}" target="_blank">STEP Bible — Todas las apariciones</a></li>
  <li><a href="https://www.blueletterbible.org/lang/lexicon/lexicon.cfm?Strongs=${w.s}&t=KJV" target="_blank">BDB/TWOT Lexicon</a></li>
`;
// Existing Greek links for NT words
else html += `...existing links...`;
```

---

## HIGH PRIORITY BUGS

### BUG-4: unified_html_generator.py `.greek-line` has no `direction:rtl` for Hebrew
**File**: `unified_html_generator.py`, line 643  
**Problem**: `.greek-line { direction: ltr implied }`. WLC Hebrew words display left-to-right (visually wrong).  
**Fix**: Add `isOT` detection and RTL styling:
```python
# In _build_unified_page JS section:
const isOT = D.parallel && D.parallel.WLC;
# In CSS:
.greek-line.heb { direction: rtl; font-family: 'SBL Hebrew', 'Ezra SIL', serif; unicode-bidi: bidi-override; }
```

---

## STRUCTURAL GAPS (unified_html_generator.py)

### GAP-1: No LXX morphology panel in unified analysis
`unified_html_generator.py` does not render `D.lxx_morphology` or `D.lxx_spanish` at all.  
**Required**: Add LXX line below Hebrew line (same pattern as study.html lines 852–858):
```javascript
if (isOT && D.lxx_morphology && D.lxx_morphology[v.v]) {
  // render LXX words with color + hover
}
if (isOT && D.lxx_spanish && D.lxx_spanish[v.v]) {
  // render LXX-ES literal Spanish
}
```

### GAP-2: WLC words in unified have no click/hover handlers
In `unified_html_generator.py`, line 751, words are rendered as plain `<span>` with no onclick/onmouseenter. The study.html `renderMorph()` adds hover tooltip and click-to-study-popup. The unified analysis doesn't have `openWordStudy` or `showWordTip` at all.

---

## DATA GAPS (No code changes needed — data pipeline issues)

| Gap | Impact | Fix Path |
|-----|--------|----------|
| `commentaries` table is NT-only | No exegetical section for any OT chapter | Ingest Keil-Delitzsch, Matthew Henry (public domain) |
| `apparatus` table is NT-only | No TC variants shown for OT | Ingest BHS critical apparatus |
| 112,974 patristic entries with `book=''` | Large patristic coverage wasted | Run verse-reference indexing pass on these entries |
| LXX Psalm numbering offset | LXX Ps 22 = Hebrew Ps 23 | Check if versification normalizer handles this |

---

## DB HEALTH (No Issues Found)

- ✅ WLC morphology: 929 chapters, 306K words — complete coverage, no gaps
- ✅ LXX morphology: 623K words, consistent with verses table
- ✅ Book name resolution: `get_all_db_names()` includes all short-form aliases (Gen, Exod, Ps, etc.)
- ✅ Hebrew Strong's lexicon: 8,674 entries indexed by Strong's H-number
- ✅ Sub-verse handling: `word_pos` is continuous within verse (no fractional verse_num in WLC)

---

## RECOMMENDED FIX ORDER

1. **BUG-3** (5 min) — Fix external links for Hebrew words (isHeb conditional)
2. **BUG-2** (10 min) — Normalize LXX dot-codes to dash-format in verbTenseEs/explainEnding  
3. **BUG-1** (2-4 hrs) — Implement full OSHM Hebrew morphology parser (`explainHebrewMorph`)  
4. **BUG-4** (30 min) — Add RTL + isOT to unified_html_generator.py  
5. **GAP-1** (2 hrs) — Port LXX morphology panel to unified_html_generator.py  
6. **GAP-2** (1 hr) — Add word hover/click handlers to unified for Hebrew words  

---

---

## ADDITIONAL CRITICAL FINDINGS (Post-Synthesis)

### BUG-CRITICAL: generate_unified_html() is DEAD CODE
`generate_unified_html()` is defined in `unified_html_generator.py` but is **never imported or called** anywhere in the codebase (`server.py`, `study_html_generator.py`, or anywhere else). All 893 lines of `unified_html_generator.py` are currently unreachable.

**To fix**: Add a call in `server.py`'s `chapter_study` tool background thread, similar to how `generate_study_html` is called, OR add a separate `unified_analysis` tool in server.py.

### BUG-HIGH: 12 LXX Book Variants Unreachable (94,675 words)
The LXX morphology table uses variant book codes that aren't in `books.py` aliases:

| LXX DB Code | Canonical Book | Words |
|-------------|---------------|-------|
| JoshA/JoshB | Joshua | 15,960 |
| JudgA/JudgB | Judges | 31,527 |
| DanOG/DanTh | Daniel | 21,234 |
| BelOG/BelTh | Daniel additions | 1,772 |
| SusOG/SusTh | Daniel additions | 1,926 |
| 1Esdr/2Esdr | Ezra/Nehemiah | 22,256 |

**Fix**: Add to `books.py` entries 6 (Joshua) and 7 (Judges) and 27 (Daniel) the extra LXX aliases:
```python
6: ("Joshua", ["Josh","Jos","Josué",..., "JoshA","JoshB"]),
7: ("Judges", ["Judg","Jdg","Jue",..., "JudgA","JudgB"]),
27: ("Daniel", ["Dan","Dn",..., "DanOG","DanTh","BelOG","BelTh","SusOG","SusTh"]),
```

### DATA CORRECTION (c2-kb was wrong on patristic OT)
c2-kb claimed "OT patristic coverage only 5037 entries". Actual: **56,863 OT patristic entries** — excellent for study (Psalms=21,625, Genesis=9,266, Isaiah=5,206, Job=4,287). The gap is in minor books (Obadiah, Jonah, Nahum etc.).

