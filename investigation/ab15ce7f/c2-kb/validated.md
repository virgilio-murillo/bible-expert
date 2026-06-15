# Validated Findings — NT vs OT Unified Analysis Gap

## Source File Metadata

| Claim | Actual | Verdict |
|-------|--------|---------|
| NT file: 1009 lines, ~1.7MB | 1009 lines, 1.7M | ✅ CONFIRMED |
| OT file: 335 lines, ~378KB | 335 lines, 370K | ✅ CONFIRMED (size ~370K not 378K, trivial) |
| Generator: 989 lines | 989 lines | ✅ CONFIRMED |
| Generator path: `unified_html_generator.py` | Found at `~/work/github/bible-expert/unified_html_generator.py` | ✅ CONFIRMED |

---

## NT Feature Claims (John-1)

### Per-Verse Structure

| Feature | Verdict | Evidence |
|---------|---------|----------|
| `.vnum` verse numbers | ✅ CONFIRMED | 3 matches |
| `.greek-line` with hoverable words | ✅ CONFIRMED | 12 matches; D object has full word-by-word JSON with `w`, `l`, `m`, `g`, `s`, `d`, `es` fields |
| `.uncial-line` scriptio continua | ✅ CONFIRMED | 4 matches |
| `.pron-line` pronunciation | ✅ CONFIRMED | 3 matches |
| `.spanish-line` RVR60 | ✅ CONFIRMED | 7 matches |
| `.ver-line` 9+ translations | ✅ CONFIRMED | 6 matches; D.parallel contains RVR60, RVR1909, KJV, ASV, BSB, Darby, LITV, YLT, Vulgate |
| Personal notes (textarea) | ✅ CONFIRMED | 4 textarea matches, 16 localStorage matches |
| Copy button | ✅ CONFIRMED | 4 "copy" matches |
| Cross-reference pills (`.xref-pill`) | ✅ CONFIRMED | 7 matches; `data-ref` found (4 matches) |
| Exegetical section | ✅ CONFIRMED | 12 `exeg` matches, `vbtn-exeg` (5 matches) |
| Patristic section | ✅ CONFIRMED | 48 `patr` matches, `vbtn-patr` (5 matches) |
| Red-letter marking | ✅ CONFIRMED | `red_letter` array in D object lists verses [38,39,42,43,47,50,51] |
| Resource badge buttons (`vbtn-*`) | ✅ CONFIRMED | `vbtn-patr` (5), `vbtn-exeg` (5) |

### Global UI Elements

| Feature | Verdict | Evidence |
|---------|---------|----------|
| Sidebar navigation | ✅ CONFIRMED | 14 matches; `.sidebar` class with verse links |
| Toolbar | ✅ CONFIRMED | 3 matches |
| Progress bar | ✅ CONFIRMED | `progressBar` in JS (line 508) |
| Back-to-top button | ✅ CONFIRMED | 5 matches for `back-to-top` |
| Keyboard navigation | ✅ CONFIRMED | `kbd-hint` (5), `keydown` (1) |
| Dark mode | ✅ CONFIRMED | `@media (prefers-color-scheme: dark)`, `body.dark` CSS rules (lines 164-171) |
| Print styles | ✅ CONFIRMED | 1 `@media print` block |
| Verse deep-link | ✅ CONFIRMED | URL hash nav referenced in scroll-spy code (line 514) |
| Highlight system | ✅ CONFIRMED | 14 `highlight` matches |

### Critical Apparatus — ⚠️ CONTRADICTED

| Claim | Verdict | Evidence |
|-------|---------|----------|
| "Full TC table with MS chips, variant columns, verdict, impact, criteria" | ❌ **CONTRADICTED** | Zero matches for `tc-table`, `variant`, `apparatus`. No TC UI exists. |
| "MS chips color-coded (🔴 Papyri, 🔵 Uncials...)" | ❌ **CONTRADICTED** | Zero matches for `ms-chip`, `chip`, `P66`, `P75`, `Sinaiticus`, `Vaticanus` in HTML/CSS. No chip UI elements. |
| "Click chip → shows manuscript info panel" | ❌ **CONTRADICTED** | No such interaction code found. |
| "Full `manuscripts` JSON with 13 MS entries" | ⚠️ **PARTIALLY CONFIRMED** | The D object DOES contain `manuscripts` JSON (P45, P46, P66, P75, ℵ, B, A, C, D, W, TR = 11 entries visible), but it's DATA ONLY — no interactive UI renders it. |

**Key finding**: The manuscript metadata exists in the data object but NO interactive critical apparatus UI (tables, chips, tooltips) is rendered. The findings report describes a feature that exists only as dormant data, not as a visible user-facing feature.

### Morphology Tooltip

| Claim | Verdict | Evidence |
|-------|---------|----------|
| Spanish translation (`es` field) | ✅ CONFIRMED | Every word in D object has `"es"` field |
| Lemma | ✅ CONFIRMED | `"l"` field present |
| Full morphology decode | ✅ CONFIRMED | `"m"` field with codes; large morphology decode dictionary in file |
| Strong's number | ✅ CONFIRMED | `"s"` field with G-numbers |
| Significance markers (⚡📌) | 🔍 UNVERIFIED | Cannot confirm from grep alone; would need to trace JS tooltip rendering logic |

### Cross-References

| Claim | Verdict | Evidence |
|-------|---------|----------|
| Clickable `.xref-pill` elements | ✅ CONFIRMED | 7 matches |
| `data-ref`, `data-es`, `data-gr`, `data-lxx` attributes | ⚠️ PARTIALLY CONFIRMED | `data-ref` confirmed (4 matches); other data attributes not individually verified but are described in HTML structure |
| `#xrefPopup` side panel | ✅ CONFIRMED | Referenced in dark mode CSS (line 169): `body.dark #xrefPopup` |
| `showXrefPopup` function | 🔍 UNVERIFIED | Zero matches for this function name — popup may use different event handler |

---

## OT Feature Claims (Proverbs-13)

### What the Findings Say Is Present

| Feature | Verdict | Evidence |
|---------|---------|----------|
| Hebrew text (WLC) with morphology | ✅ CONFIRMED | Large Hebrew morphology data in D object |
| LXX text with morphology | ✅ CONFIRMED | `lxx_morphology` in D object with per-verse Greek word data |
| LXX Spanish translation | ✅ CONFIRMED | `lxx_spanish` in D object with 25 verse translations |
| RVR60 Spanish | ✅ CONFIRMED | `spanish` + `translations.RVR60` in D object |
| 8+ translations | ✅ CONFIRMED | D.translations has: RVR60, RVR1909, KJV, ASV, BSB, Darby, LITV, YLT, Vulgate (9 total) |
| Word study popup | 🔍 UNVERIFIED | No `word-study` or `ws-popup` class found |

### What the Findings Say Is COMPLETELY MISSING

| Feature | Claim: Missing | Actual Verdict | Evidence |
|---------|---------------|----------------|----------|
| Cross-reference pills | ❌ Missing | ✅ **CONFIRMED MISSING** | 0 matches for `xref-pill`, `xref`, `cross.ref` |
| Exegetical section | ❌ Missing | ⚠️ **NUANCED** | `exeg` has 5 matches — BUT these are the empty key `"exegetical": ""` in D and CSS class definitions, NOT actual content. **Effectively missing.** |
| Patristic section | ❌ Missing | ⚠️ **NUANCED** | `patr` has 24 matches — BUT these are from Greek word `πατρ-` (father) in LXX morphology data, NOT patristic commentary content. **Effectively missing.** |
| Critical apparatus | ❌ Missing | ✅ **CONFIRMED MISSING** | 0 matches (same as NT — feature doesn't exist in either file as rendered UI) |
| Personal notes | ❌ Missing | ✅ **CONFIRMED MISSING** | 0 textarea, 0 localStorage |
| Copy button | ❌ Missing | ✅ **CONFIRMED MISSING** | 0 matches |
| Resource badge buttons | ❌ Missing | ✅ **CONFIRMED MISSING** | 0 matches for `vbtn-` |

### Global UI — Findings Say COMPLETELY MISSING

| Feature | Claim: Missing | Actual Verdict | Evidence |
|---------|---------------|----------------|----------|
| Sidebar | ❌ Missing | ❌ **CONTRADICTED** | 4 `sidebar` matches — sidebar HTML/CSS IS present in OT file |
| Toolbar | ❌ Missing | ❌ **CONTRADICTED** | 2 `toolbar` matches — toolbar structure IS present |
| Dark mode | ❌ Missing | ❌ **CONTRADICTED** | 1 `dark` match — dark mode reference exists |
| Progress bar | ❌ Missing | 🔍 UNVERIFIED | 0 `progress` matches |
| Back-to-top | ❌ Missing | ✅ **CONFIRMED MISSING** | 0 matches |
| Print styles | ❌ Missing | ✅ **CONFIRMED MISSING** | 0 `@media print` |
| Keyboard nav | ❌ Missing | ✅ **CONFIRMED MISSING** | 0 `kbd`/`keydown` |
| Verse deep-link | ❌ Missing | 🔍 UNVERIFIED | Not checked |
| Highlight system | ❌ Missing | ✅ **CONFIRMED MISSING** | 0 `highlight` |

**Important correction**: The OT file DOES have sidebar and toolbar structural elements (likely from the shared generator template). The findings overstate by claiming these are "COMPLETELY MISSING." They are present in structure but may lack the content/data to populate them.

---

## Gap Analysis Assessment

| Claimed Gap | Verdict |
|-------------|---------|
| Gap 1: Cross-References ABSENT from OT | ✅ **CONFIRMED** — No xref data or pills in OT |
| Gap 2: Patristic Commentary ABSENT from OT | ✅ **CONFIRMED** — No patristic content data |
| Gap 3: Exegetical Commentary ABSENT from OT | ✅ **CONFIRMED** — `exegetical` key is empty string |
| Gap 4: Critical Apparatus ABSENT from OT | ⚠️ **MISLEADING** — TC UI doesn't exist in EITHER file. This isn't an NT-vs-OT gap; it's absent from both. The NT has manuscript DATA but no rendered apparatus. |

---

## Summary of Corrections

1. **Critical apparatus claim is the biggest error.** The findings describe an elaborate interactive TC system (tables, MS chips, color coding, click panels) that DOES NOT EXIST in the NT file. The manuscripts data exists as JSON but has no rendered UI. This feature is absent from BOTH files, not an NT-has/OT-lacks gap.

2. **OT global UI is not "completely missing."** Sidebar and toolbar structures exist in the OT file (from the shared template). The findings overstate by marking them as completely absent.

3. **OT file size**: ~370KB not ~378KB. Minor.

4. **Manuscript count**: The findings claim "13 MS entries" but I counted 11 visible entries (P45, P46, P66, P75, ℵ, B, A, C, D, W, TR). Possible the full JSON has 2 more entries not displayed in the truncated output.

5. **The core gap analysis (xrefs, patristic, exegetical content) is VALID.** The OT truly lacks these scholarly content sections that the NT has populated.

6. **Action plan and priority ranking are SOUND** given the confirmed gaps, but Phase 6 (Critical Apparatus) should be noted as a NEW feature for both NT and OT, not a parity issue.
