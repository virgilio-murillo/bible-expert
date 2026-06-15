# NT vs OT Unified Analysis — Complete Gap Analysis

## Source Files Analyzed
- **NT reference**: `~/bible-studies/John-1/unified_analysis.html` (1.7MB)
- **OT current**: `~/bible-studies/Proverbs-13/unified_analysis.html` (378KB)

---

## 1. CROSS-REFERENCES — The #1 Gap (User Priority)

### NT (John 1) — How Xrefs Work:
- **INLINE in each verse block** as `xref-pill` elements (blue rounded pills)
- Each pill has `data-es` (Spanish RVR text), `data-gr` (Greek MorphGNT text), `data-lxx` (LXX Greek for OT refs)
- Clicking a pill calls `showXrefPopup(el)` which reads all data-* attributes and shows a popup with multilingual text
- **3 languages visible in popup**: Spanish, Greek NT, LXX Greek
- The pills are inside an `xref-container` div, toggled by a `🔗 N refs` button
- Example: `<span class="xref-pill" onclick="showXrefPopup(this)" data-ref="John 4:29" data-es="Venid, ved..." data-gr="Δεῦτε ἴδετε..." data-lxx="">John 4:29</span>`

### OT (Proverbs 13) — Current State:
- Xrefs in **sidebar only** (listed by verse number) — clicking calls `showXrefPopup('Proverbs 15:5','')` with empty second arg
- Inside verse blocks: xrefs are in a **collapsed `section-content`** div toggled by a badge
- Shows only Spanish text via `xref-entry` div: `<div class="xref-entry"><strong>Proverbs 15:5</strong>: El necio menosprecia...</div>`
- **NO Greek text, NO Hebrew text, NO LXX text** in the xref data
- The `xrefs` array in JSON data has `text.es` and `text.gr` — but `gr` is often empty for OT-to-OT refs (only populated for NT refs like James, Matthew)

### What's Needed:
1. Add `xref-pill` + `xref-container` CSS classes (already in OT CSS but unused in HTML)
2. Change xref rendering from `<div class="xref-entry">` to `<span class="xref-pill" data-ref="..." data-es="..." data-gr="..." data-heb="..." data-lxx="...">` 
3. For OT-to-OT xrefs: populate `data-heb` (WLC text) and `data-lxx` (LXX Greek text)
4. For OT-to-NT xrefs: populate `data-gr` (MorphGNT text)
5. Add 4th language: **Hebrew (WLC)** — the user wants 4 languages: Spanish, Hebrew, Greek (LXX or MorphGNT), English (KJV/BSB)
6. Modify `showXrefPopup` to display all 4 languages in a styled popup

---

## 2. VERSE BLOCK FEATURES — Per-Verse Buttons & Sections

### NT (John 1) has these per-verse interactive buttons:
| Button | Function | OT Has? |
|--------|----------|---------|
| `RVR60` | Toggle Spanish translation | ❌ No (RVR shown inline always) |
| `Uncial` | Show scriptio continua (ALL CAPS, no spaces) with Codex Sinaiticus link | ❌ MISSING |
| `Pronunciación` | Byzantine pronunciation guide | ❌ MISSING |
| `✝ N patrística` | Toggle patristic section | ✅ Has (as badge) |
| `📚 N exégesis` | Toggle exegesis section | ❌ MISSING entirely |
| `📖 versiones` | Toggle parallel translations (9 versions) | ❌ MISSING (no toggle) |
| `🔗 N refs` | Toggle inline cross-references | ✅ Has (as badge) |
| `📋 Copy` | Copy verse to clipboard | ❌ MISSING |
| `📝 Notes` | Personal notes textarea (saved to localStorage) | ❌ MISSING |

### OT (Proverbs 13) verse block structure:
- Verse number → RVR text → WLC line (empty!) → LXX line (empty!) → LXX-ES translation → badges row → collapsed sections

### NT (John 1) verse block structure:
- Verse number + red-letter indicator → Greek (MorphGNT) → Uncial (hidden) → Button row (RVR60, Uncial, Pron, Patr, Exeg, Ver, Refs, Copy, Notes) → collapsed Spanish → collapsed versions → inline xref pills → pronunciation → notes textarea → Exegesis section → Patristic section

---

## 3. EXEGESIS SECTION — Completely Missing from OT

### NT has per-verse:
- `section-toggle` with `📜 Exégesis del Griego`
- `exeg-summary` with highlighted quotes from 3 commentators (Alford, Bengel, Robertson)
- Expandable `comm-item` blocks for each commentator (full commentary text)
- `themes-divider` + `theme-card` showing debated topics with consensus bars
- Each theme has `opinion` entries with agreement indicators (✅/⚠️)
- A `theme-summary` summarizing the scholarly consensus

### OT status: **COMPLETELY ABSENT** — no exegetical commentary at all

---

## 4. UI/UX FEATURES — Missing from OT

| Feature | NT | OT |
|---------|----|----|
| Dark mode CSS | ✅ Full `@media (prefers-color-scheme: dark)` | ❌ Missing |
| Progress bar (scroll) | ✅ `.progress-bar` fixed top | ❌ Missing |
| Back-to-top button | ✅ `.back-to-top` with visibility toggle | ❌ Missing |
| Keyboard navigation hint | ✅ `.kbd-hint` | ❌ Missing |
| Red-letter (Verba Christi) | ✅ `.red-letter .greek-line { color: #c62828 }` | N/A (OT) |
| Verse deep-link `:target` | ✅ `#vb1` highlight animation | ❌ Missing |
| Print styles | ✅ `@media print` hides toolbar, expands all | ❌ Missing |
| Smooth scroll | ✅ `html { scroll-behavior: smooth }` | ❌ Missing |
| Focus-visible accessibility | ✅ `:focus-visible { outline... }` | ❌ Missing |
| Font preload | ✅ `<link rel="preload">` | ❌ Missing |
| Resource badge buttons (colored) | ✅ `.vbtn-patr`, `.vbtn-exeg`, `.vbtn-ver` | ❌ Missing |
| Uncial script view | ✅ Scriptio continua with Sinaiticus links | ❌ Missing |
| Byzantine pronunciation | ✅ Toggle per verse | ❌ Missing |
| Copy verse button | ✅ Copies formatted text | ❌ Missing |
| Personal notes (localStorage) | ✅ Textarea per verse, auto-saved | ❌ Missing |

---

## 5. MORPHOLOGY — Both Have It, OT Has Richer Data

### NT: Word-by-word Greek with hover tooltips showing lemma, parsing, Strong's
### OT: Word-by-word Hebrew (WLC) + LXX morphology — **DATA EXISTS** in JSON but...
- Hebrew morphology renders via JavaScript but **WLC line shows empty** (`id="greek-1" dir="rtl"`) because the DOM element is empty and filled by JS
- LXX morphology is fully populated in `lxx_morphology` data
- The OT actually has MORE morphological data (Hebrew + LXX) than the NT (just Greek)

### Problem: The WLC text line and LXX text line appear **empty** in the rendered HTML — the JS populates them dynamically but only for Hebrew. LXX line seems to NOT get populated.

---

## 6. TRANSLATIONS — OT Data Is Complete But Not Togglable

### NT: 9 translations accessible via `📖 versiones` button, hidden by default
### OT: Has the same 9 translations in `D.translations` JSON data (RVR60, RVR1909, KJV, ASV, BSB, Darby, LITV, YLT, Vulgate) — but **no toggle button** to show them. No `vers-N` div in the HTML.

---

## 7. PATRISTIC SECTION — OT Has It, But Slightly Less Polished

### NT: 
- Themed patristic citations with consensus bars
- Each theme is collapsible with arrow
- Father name + century + meta info + Wikipedia link + verse ref
- `patr-resumen` summary at end of each theme
- Reliability indicators (✅ high confidence, ⚠️ moderate)

### OT: 
- ✅ Same structure with themes, citations, consensus bars, resumen
- ✅ Father metadata (century, city, Wikipedia link)
- Slightly less polished presentation but functionally equivalent

---

## 8. CRITICAL APPARATUS — NT Has Full TC Tables, OT Has None

### NT has:
- Interactive `tc-table` with manuscript chips (hoverable, showing full ms info)
- `tc-verdict` section with textual criticism verdict
- `tc-criteria-expanded` showing evaluation criteria
- `tc-interactive` cells with hover effects
- Full manuscript database in `D.manuscripts`

### OT: Has `D.apparatus` as empty array `[]` — no TC data at all. This is expected for Proverbs (no major OT textual variants in the critical apparatus for this chapter).

---

## 9. ACTION PLAN — Bringing OT to Full Parity

### Priority 1: INLINE CROSS-REFERENCES with 4 Languages (HIGH — User's #1 Request)

**In `unified_html_generator.py`:**
1. Modify `_render_xrefs` to output `xref-pill` spans instead of `xref-entry` divs
2. For each xref, look up the referenced verse text in:
   - Spanish (RVR60) — already available
   - Hebrew (WLC) — query from DB for OT refs
   - Greek (LXX for OT refs, MorphGNT for NT refs) — query from DB
   - English (KJV or BSB) — query from DB
3. Embed as `data-es`, `data-heb`, `data-gr`, `data-en` attributes
4. Add a `showXrefPopup` JS function that renders a styled 4-language popup

### Priority 2: EXEGESIS SECTION (HIGH — Missing Entirely)

**In `unified_html_generator.py`:**
1. Add exegetical commentary data source (same commentators: Alford/Bengel/Robertson have OT coverage? or use Keil & Delitzsch, Matthew Henry, etc.)
2. Add `_render_exegesis` method generating `exeg-section` with summary + expandable commentators
3. Add theme cards with consensus analysis

### Priority 3: PER-VERSE INTERACTIVE BUTTONS (MEDIUM)

**In `unified_html_generator.py` → `_render_verse_block`:**
1. Add button row with: `📖 versiones`, `📋 Copy`, `📝 Notes`
2. Add `vers-N` div with all 9 translations (collapsed by default)
3. Add copy-to-clipboard JS function
4. Add notes textarea with localStorage persistence

### Priority 4: UI/UX FEATURES (MEDIUM)

**In `unified_html_generator.py` → CSS/HTML template:**
1. Add dark mode CSS (copy from NT)
2. Add progress bar div + scroll listener JS
3. Add back-to-top button + visibility toggle
4. Add smooth scroll CSS
5. Add print styles
6. Add focus-visible accessibility
7. Add font preload link

### Priority 5: FIX EMPTY WLC/LXX TEXT LINES (HIGH — Data Exists But Not Rendering)

**In `unified_html_generator.py`:**
1. The WLC and LXX text lines are rendered as empty divs with IDs — they get populated by JS
2. Verify the JavaScript correctly populates these from `D.parallel.WLC` and `D.parallel.LXX`
3. If JS is broken, render the text server-side directly into the HTML

### Priority 6: UNCIAL VIEW (LOW — Aesthetic but Nice)

Not applicable for OT Hebrew, but could show:
- Paleo-Hebrew script view for historical interest
- LXX uncial (all-caps Greek) for the Septuagint text

### Priority 7: PRONUNCIATION (LOW)

Could add:
- Tiberian Hebrew pronunciation guide
- Byzantine Greek pronunciation for LXX text

---

## Summary of Gap Severity

| Feature | Severity | Effort |
|---------|----------|--------|
| Inline xrefs with 4 languages | 🔴 Critical | Medium (DB queries + popup) |
| Exegesis section | 🔴 Critical | High (need commentary data) |
| Version toggle per verse | 🟡 High | Low (data exists, add button + div) |
| Copy + Notes buttons | 🟡 High | Low (JS only) |
| Empty WLC/LXX text lines | 🟡 High | Low (JS fix or server-side render) |
| Dark mode + progress bar + back-to-top | 🟢 Medium | Low (CSS copy) |
| Print styles + accessibility | 🟢 Medium | Low (CSS copy) |
| Uncial/Pronunciation | ⚪ Low | Medium |
