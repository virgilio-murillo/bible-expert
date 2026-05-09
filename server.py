"""Bible Expert MCP Server — Comprehensive biblical research tools."""
import json
import os
import sqlite3
from pathlib import Path
from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).parent / "db" / "bible.db"
DATA_DIR = Path(__file__).parent / "data"

mcp = FastMCP("Bible-Expert")


def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@mcp.tool()
def verse_lookup(reference: str, version: str = "SBLGNT", include_morphology: bool = False) -> str:
    """Look up Bible verse(s) by canonical reference (RVR60/Hebrew numbering). Supports all loaded versions.
    
    Args:
        reference: Canonical reference in RVR60 numbering like "Gen 1:1", "John 3:16-18", "Psalms 23:1"
        version: Text version. Options: MorphGNT, LXX, WLC, RVR1960, YLT, Vulgate, ApostolicFathers
        include_morphology: Include word-level morphological parsing (Greek/Hebrew only)
    """
    db = get_db()
    try:
        book, chap_verse = _parse_reference(reference)
        chapter, verse_start, verse_end = _parse_chap_verse(chap_verse)
        
        rows = _query_verse(db, book, chapter, verse_start, verse_end, version)
        
        if not rows:
            return f"No results for {reference} in {version}. Available versions: " + _list_versions(db)
        
        result = f"**{reference}** ({version}):\n\n"
        
        # Add versification note
        note = _get_versification_note(book, chapter, verse_start, version)
        if note:
            result += f"_{note}_\n\n"
        
        for r in rows:
            result += f"  {r['verse_num']}. {r['text']}\n"
            if include_morphology and r['morphology']:
                result += f"     Morphology: {r['morphology']}\n"
        return result
    finally:
        db.close()


@mcp.tool()
def parallel_versions(reference: str, versions: list[str] | None = None) -> str:
    """Show a verse in multiple translations side-by-side. Uses RVR60/Hebrew numbering as canonical.
    
    Args:
        reference: Canonical verse reference in RVR60 numbering like "John 1:1", "Psalms 23:1"
        versions: List of versions to compare. Default: MorphGNT, LXX, WLC, RVR1960, YLT, Vulgate
    """
    if versions is None:
        versions = ["MorphGNT", "LXX", "WLC", "RVR1960", "YLT", "Vulgate"]
    
    db = get_db()
    try:
        book, chap_verse = _parse_reference(reference)
        chapter, verse_start, verse_end = _parse_chap_verse(chap_verse)
        
        result = f"**{reference}** — Parallel Comparison:\n"
        
        # Add versification note if applicable
        note = _get_versification_note(book, chapter, verse_start, "LXX")
        if note:
            result += f"\n_{note}_\n"
        
        result += "\n"
        for ver in versions:
            rows = _query_verse(db, book, chapter, verse_start, verse_end, ver)
            text = " ".join(r['text'] for r in rows) if rows else "(not available)"
            result += f"**{ver}**: {text}\n\n"
        return result
    finally:
        db.close()


@mcp.tool()
def semantic_search(query: str, scope: str = "all", limit: int = 10) -> str:
    """Search biblical texts by meaning using semantic similarity.
    
    Args:
        query: Natural language query in any language (Spanish, English, Greek, Hebrew)
        scope: Filter scope. Options: all, ot, nt, deuterocanonical, pseudepigrapha, dss, apocryphal, apostolic_fathers
        limit: Max results to return (default 10)
    """
    db = get_db()
    try:
        # Check if embeddings are available
        has_vec = db.execute("SELECT count(*) FROM sqlite_master WHERE name='verse_embeddings'").fetchone()[0]
        if not has_vec:
            return _fts_search(db, query, scope, limit)
        
        try:
            import sqlite_vec
            from sentence_transformers import SentenceTransformer
            
            db.enable_load_extension(True)
            sqlite_vec.load(db)
            
            model = _get_embedding_model()
            embedding = model.encode(query)
            
            scope_filter = _scope_to_sql(scope)
            if scope_filter:
                scope_filter = "AND " + scope_filter.replace("WHERE ", "")
            
            rows = db.execute(f"""
                SELECT v.book, v.chapter, v.verse_num, v.version, v.text, v.canon_status, e.distance
                FROM verse_embeddings e
                JOIN verses v ON e.verse_id = v.id
                WHERE e.embedding MATCH ? AND k = ?
                {scope_filter}
            """, (embedding.tobytes(), limit)).fetchall()
            
            result = f"**Semantic search**: \"{query}\" (scope: {scope})\n\n"
            for i, r in enumerate(rows, 1):
                result += f"{i}. [{r[0]} {r[1]}:{r[2]}] ({r[3]}) — {r[4][:200]}\n"
                result += f"   Canon: {r[5] or 'N/A'} | Distance: {r[6]:.4f}\n\n"
            return result if rows else "No results found."
        except (ImportError, Exception) as e:
            # Fallback to FTS
            return _fts_search(db, query, scope, limit)
    finally:
        db.close()


@mcp.tool()
def morphology_analysis(reference: str, version: str = "MorphGNT") -> str:
    """Get detailed word-by-word morphological analysis for a verse.
    
    Args:
        reference: Verse reference like "John 1:1"
        version: Morphological source. Options: MorphGNT (Greek NT), WLC (Hebrew OT), LXX
    """
    db = get_db()
    try:
        book, chap_verse = _parse_reference(reference)
        chapter, verse_start, verse_end = _parse_chap_verse(chap_verse)
        
        # Try multiple book name variants
        rows = []
        for b in _normalize_book(book, version):
            rows = db.execute(
                "SELECT word_pos, word, lemma, morph_code, gloss, strongs FROM morphology "
                "WHERE book=? AND chapter=? AND verse_num BETWEEN ? AND ? AND version=? "
                "ORDER BY verse_num, word_pos",
                (b, chapter, verse_start, verse_end, version)
            ).fetchall()
            if rows:
                break
        
        if not rows:
            return f"No morphological data for {reference} in {version}."
        
        result = f"**Morphology: {reference}** ({version}):\n\n"
        result += "| # | Word | Lemma | Parsing | Gloss | Strong's |\n|---|------|-------|---------|-------|----------|\n"
        for r in rows:
            result += f"| {r['word_pos']} | {r['word']} | {r['lemma']} | {r['morph_code']} | {r['gloss'] or ''} | {r['strongs'] or ''} |\n"
        return result
    finally:
        db.close()


@mcp.tool()
def critical_apparatus(reference: str) -> str:
    """Get textual variants and manuscript evidence for a verse.
    
    Args:
        reference: Verse reference like "John 7:53" or "Mark 16:9"
    """
    db = get_db()
    try:
        book, chap_verse = _parse_reference(reference)
        chapter, verse_start, verse_end = _parse_chap_verse(chap_verse)
        
        rows = db.execute(
            "SELECT verse_num, variant_id, reading, manuscripts, text_type, notes FROM apparatus "
            "WHERE book=? AND chapter=? AND verse_num BETWEEN ? AND ? "
            "ORDER BY verse_num, variant_id",
            (book, chapter, verse_start, verse_end)
        ).fetchall()
        
        if not rows:
            return f"No apparatus data for {reference}. This verse may have no significant variants in our database."
        
        result = f"**Critical Apparatus: {reference}**\n\n"
        current_variant = None
        for r in rows:
            vid = f"{r['verse_num']}.{r['variant_id']}"
            if vid != current_variant:
                current_variant = vid
                result += f"\n### Variant at v.{r['verse_num']} #{r['variant_id']}:\n"
            result += f"- **Reading**: {r['reading']}\n"
            result += f"  Manuscripts: {r['manuscripts']}\n"
            if r['text_type']:
                result += f"  Text-type: {r['text_type']}\n"
            if r['notes']:
                result += f"  Notes: {r['notes']}\n"
        return result
    finally:
        db.close()


@mcp.tool()
def patristic_commentary(reference: str, fathers: list[str] | None = None) -> str:
    """Get patristic commentary on a verse from the Church Fathers.
    Shows the original language (Greek/Latin) when available, plus English translation.
    
    Args:
        reference: Verse reference like "Romans 9:13"
        fathers: Filter by specific fathers. E.g. ["Chrysostom", "Augustine", "Origen"]. Default: all available.
    """
    db = get_db()
    try:
        book, chap_verse = _parse_reference(reference)
        chapter, verse_start, verse_end = _parse_chap_verse(chap_verse)
        
        query = """SELECT father, work, text, text_original, original_lang, date_approx 
                   FROM patristic WHERE book=? AND chapter=? AND verse_num BETWEEN ? AND ?"""
        params: list = [book, chapter, verse_start, verse_end]
        
        # Try normalized book names
        candidates = _normalize_book(book, "")
        rows = []
        for b in candidates:
            if fathers:
                # Use LIKE for each father name (they may be partial matches)
                father_clauses = " OR ".join(["father LIKE ?" for _ in fathers])
                q = query + f" AND ({father_clauses})"
                p = [b, chapter, verse_start, verse_end] + [f"%{f}%" for f in fathers]
            else:
                q = query
                p = [b, chapter, verse_start, verse_end]
            q += " ORDER BY (text_original IS NOT NULL) DESC, date_approx LIMIT 20"
            rows = db.execute(q, p).fetchall()
            if rows:
                break
        
        if not rows:
            return f"No patristic commentary found for {reference}."
        
        result = f"**Patristic Commentary: {reference}**\n\n"
        for r in rows:
            lang_tag = f" [{r['original_lang'].upper()}]" if r['original_lang'] else ""
            result += f"### {r['father']}{lang_tag} ({r['date_approx'] or '?'})\n"
            result += f"*{r['work']}*\n\n"
            
            # Show original text if available (Greek/Latin)
            if r['text_original']:
                result += f"**Original ({r['original_lang']}):**\n{r['text_original'][:800]}\n\n"
                result += f"**English translation:**\n{r['text'][:800]}\n\n"
            else:
                # We only have the English translation
                result += f"**English translation:**\n{r['text'][:1000]}\n\n"
                result += f"⚠️ _Original {r['original_lang']} text not in database. Use web_search to find the original from Migne PG/PL, TLG, or Perseus. Search: \"{r['father']} {r['work']} greek/latin original text\"_\n"
            
            result += "\n---\n\n"
        
        # Also check if there's Greek text from Apostolic Fathers for this reference
        af_rows = db.execute(
            "SELECT book, text FROM verses WHERE version='ApostolicFathers' AND book LIKE ? AND chapter=? AND verse_num BETWEEN ? AND ?",
            (f"%{book}%", chapter, verse_start, verse_end)
        ).fetchall()
        if af_rows:
            result += "### Original Greek (Apostolic Fathers)\n"
            for r in af_rows:
                result += f"**{r['book']}** {chapter}:{verse_start}:\n{r['text'][:500]}\n\n"
        
        # If we didn't find entries with original text, search the unindexed originals
        has_originals = any(r['text_original'] for r in rows)
        if not has_originals:
            # Search Greek/Latin originals that mention this book/chapter
            book_search = book[:4]  # short form for searching in Greek/Latin text
            orig_rows = db.execute(
                "SELECT father, work, text_original, original_lang FROM patristic "
                "WHERE text_original LIKE ? AND original_lang IS NOT NULL LIMIT 5",
                (f"%{book_search}%{chapter}%",)
            ).fetchall()
            if orig_rows:
                result += "\n### Additional Original Texts (unindexed, possibly relevant)\n"
                for r in orig_rows:
                    result += f"**{r['father']}** [{r['original_lang'].upper()}] *{r['work']}*:\n{r['text_original'][:400]}\n\n"
        
        return result
    finally:
        db.close()


@mcp.tool()
def cross_references(reference: str, include_intertextual: bool = True) -> str:
    """Get cross-references and intertextual connections for a verse.
    
    Args:
        reference: Verse reference like "Hebrews 1:3"
        include_intertextual: Include connections to pseudepigrapha, DSS, and apocrypha (default true)
    """
    db = get_db()
    try:
        book, chap_verse = _parse_reference(reference)
        chapter, verse_start, verse_end = _parse_chap_verse(chap_verse)
        
        # Try multiple book name variants
        rows = []
        for b in _normalize_book(book, ""):
            rows = db.execute(
                "SELECT target_ref, relationship, notes, target_canon_status FROM cross_refs "
                "WHERE source_book=? AND source_chapter=? AND source_verse BETWEEN ? AND ? "
                "ORDER BY relationship, target_ref",
                (b, chapter, verse_start, verse_end)
            ).fetchall()
            if rows:
                break
        
        if not include_intertextual:
            rows = [r for r in rows if r['target_canon_status'] in ('protocanonical', 'deuterocanonical')]
        
        if not rows:
            return f"No cross-references found for {reference}."
        
        result = f"**Cross-References: {reference}**\n\n"
        current_rel = None
        for r in rows:
            if r['relationship'] != current_rel:
                current_rel = r['relationship']
                result += f"\n**{current_rel}**:\n"
            canon_tag = f" [{r['target_canon_status']}]" if r['target_canon_status'] != 'protocanonical' else ""
            result += f"- {r['target_ref']}{canon_tag}"
            if r['notes']:
                result += f" — {r['notes']}"
            result += "\n"
        return result
    finally:
        db.close()


@mcp.tool()
def word_study(word: str, language: str = "greek") -> str:
    """Deep study of a biblical word: definition, etymology, frequency, all occurrences.
    
    Args:
        word: The word to study (Greek, Hebrew, or English gloss). Can also be a Strong's number like "G26" or "H430".
        language: Source language. Options: greek, hebrew
    """
    import unicodedata
    db = get_db()
    try:
        row = None
        # Search by Strong's number
        if word.upper().startswith(("G", "H")) and word[1:].isdigit():
            num = int(word[1:])
            row = db.execute("SELECT * FROM lexicon WHERE strongs=?", (f"G{num}",)).fetchone()
            if not row:
                row = db.execute("SELECT * FROM lexicon WHERE strongs=?", (f"H{num}",)).fetchone()
        
        if not row:
            # Normalize input and search by normalized lemma
            normalized = ''.join(c for c in unicodedata.normalize('NFD', word) if unicodedata.category(c) != 'Mn').lower()
            row = db.execute("SELECT * FROM lexicon WHERE lemma_normalized=?", (normalized,)).fetchone()
        
        if not row:
            # Search by gloss
            row = db.execute("SELECT * FROM lexicon WHERE gloss LIKE ?", (f"%{word}%",)).fetchone()
        
        if not row:
            return f"Word '{word}' not found in lexicon. Try a Strong's number (G3056, H430) or Greek/Hebrew lemma."
        
        result = f"**Word Study: {row['lemma']}** ({row['strongs']})\n\n"
        result += f"- **Gloss**: {row['gloss']}\n"
        result += f"- **Definition**: {row['definition']}\n"
        result += f"- **Etymology/Derivation**: {row['etymology'] or 'N/A'}\n"
        result += f"- **Transliteration/Root**: {row['root'] or 'N/A'}\n\n"
        return result
    finally:
        db.close()


@mcp.tool()
def authenticity_report(text_name: str) -> str:
    """Gather all available evidence about a text's authenticity from the database.
    Returns: manuscript evidence (DSS fragments, versions available), patristic citations,
    canonical history, and cross-references. The agent synthesizes the assessment.
    
    Args:
        text_name: Name of the text. E.g. "1 Enoch", "Gospel of Thomas", "Didache", "Mark 16:9-20", "1QS"
    """
    db = get_db()
    try:
        result = f"# Evidence for: {text_name}\n\n"
        
        # Check if it's a DSS scroll
        dss_count = db.execute("SELECT count(*) FROM dss WHERE scroll_id LIKE ?", (f"%{text_name}%",)).fetchone()[0]
        if dss_count:
            result += f"## Dead Sea Scrolls Evidence\n- Found {dss_count} lines in DSS database under scroll ID matching '{text_name}'\n"
            sample = db.execute("SELECT scroll_id, text FROM dss WHERE scroll_id LIKE ? LIMIT 3", (f"%{text_name}%",)).fetchall()
            for r in sample:
                result += f"  - [{r[0]}]: {r[1][:100]}...\n"
            result += "\n"
        
        # Check available versions
        versions = db.execute(
            "SELECT version, count(*) FROM verses WHERE book LIKE ? GROUP BY version",
            (f"%{text_name}%",)
        ).fetchall()
        if versions:
            result += "## Available Text Versions\n"
            for v in versions:
                result += f"- {v[0]}: {v[1]} verses\n"
            result += "\n"
        
        # Check patristic citations
        patristic = db.execute(
            "SELECT father, work, text FROM patristic WHERE book LIKE ? LIMIT 5",
            (f"%{text_name}%",)
        ).fetchall()
        if patristic:
            result += "## Patristic Citations\n"
            for p in patristic:
                result += f"- **{p[0]}** ({p[1]}): {p[2][:200]}...\n"
            result += "\n"
        
        # Check canon history
        canon = db.execute(
            "SELECT date_event, event, tradition, decision FROM canon_history WHERE book LIKE ? ORDER BY date_event",
            (f"%{text_name}%",)
        ).fetchall()
        if canon:
            result += "## Canon History\n"
            for c in canon:
                result += f"- {c[0]}: {c[1]} ({c[2]}) — {c[3]}\n"
            result += "\n"
        
        # Check cross-references pointing to this text
        xrefs = db.execute(
            "SELECT source_book, source_chapter, source_verse, relationship, notes FROM cross_refs WHERE target_ref LIKE ? LIMIT 10",
            (f"%{text_name}%",)
        ).fetchall()
        if xrefs:
            result += "## Cross-References (canonical texts citing this)\n"
            for x in xrefs:
                result += f"- {x[0]} {x[1]}:{x[2]} ({x[3]}): {x[4] or ''}\n"
            result += "\n"
        
        if not any([dss_count, versions, patristic, canon, xrefs]):
            result += "(No structured data found in database. Use web_search for external research on this text's authenticity.)\n"
        
        return result
    finally:
        db.close()


@mcp.tool()
def dss_lookup(scroll_id: str = "", keyword: str = "") -> str:
    """Search Dead Sea Scrolls texts by scroll ID or keyword.
    
    Args:
        scroll_id: Scroll identifier like "1QS", "1QIsaa", "4QMMT", "11QMelch". Leave empty to list available scrolls.
        keyword: Search keyword within DSS texts. Use Hebrew (e.g. "אור", "דבר", "יחד") for best results. English keywords search transliterated text.
    """
    db = get_db()
    try:
        if not scroll_id and not keyword:
            rows = db.execute("SELECT scroll_id, count(*) as lines FROM dss GROUP BY scroll_id ORDER BY lines DESC LIMIT 30").fetchall()
            result = "**Available Dead Sea Scrolls** (top 30 by size):\n\n"
            for r in rows:
                result += f"- **{r[0]}**: {r[1]} lines\n"
            result += "\nUse scroll_id for full text, or keyword in Hebrew (e.g. 'אור', 'דבר', 'משיח') to search across all scrolls."
            return result
        
        if scroll_id:
            rows = db.execute(
                "SELECT scroll_id, line_num, text FROM dss WHERE scroll_id=? ORDER BY line_num LIMIT 50",
                (scroll_id,)
            ).fetchall()
            if not rows:
                # Try case-insensitive
                rows = db.execute(
                    "SELECT scroll_id, line_num, text FROM dss WHERE scroll_id LIKE ? ORDER BY line_num LIMIT 50",
                    (f"%{scroll_id}%",)
                ).fetchall()
        else:
            rows = db.execute(
                "SELECT scroll_id, line_num, text FROM dss WHERE text LIKE ? ORDER BY scroll_id, line_num LIMIT 20",
                (f"%{keyword}%",)
            ).fetchall()
        
        if not rows:
            return f"No results for scroll_id='{scroll_id}', keyword='{keyword}'. Try Hebrew keywords: אור (light), חושך (darkness), דבר (word), משיח (messiah), יחד (community)."
        
        result = f"**DSS: {scroll_id or f'keyword \"{keyword}\"'}**\n\n"
        for r in rows:
            result += f"[{r[0]} L{r[1]}] {r[2]}\n"
        return result
    finally:
        db.close()


@mcp.tool()
def canon_history(book_name: str) -> str:
    """Get the canonical history of a book: who accepted it, who rejected it, when, and why.
    
    Args:
        book_name: Name of the book. E.g. "Hebrews", "Revelation", "1 Enoch", "Shepherd of Hermas", "Jasher"
    """
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM canon_history WHERE book=? OR book LIKE ? ORDER BY date_event",
            (book_name, f"%{book_name}%")
        ).fetchall()
        
        if not rows:
            return f"No canonical history for '{book_name}'."
        
        result = f"# Canonical History: {book_name}\n\n"
        result += "| Date | Event | Tradition | Decision | Source |\n|------|-------|-----------|----------|--------|\n"
        for r in rows:
            result += f"| {r['date_event']} | {r['event']} | {r['tradition']} | {r['decision']} | {r['source']} |\n"
        return result
    finally:
        db.close()


@mcp.tool()
def text_comparison(ref1: str, ref2: str, version1: str = "WLC", version2: str = "LXX") -> str:
    """Compare two parallel passages or the same passage in different textual traditions.
    Useful for MT vs LXX, MT vs DSS, Synoptic parallels, etc.
    
    Args:
        ref1: First reference (e.g. "Isaiah 7:14")
        ref2: Second reference (e.g. "Isaiah 7:14") — can be same verse different version, or a parallel passage
        version1: Version for ref1 (default WLC)
        version2: Version for ref2 (default LXX)
    """
    db = get_db()
    try:
        text1 = _get_verse_text(db, ref1, version1)
        text2 = _get_verse_text(db, ref2, version2)
        
        result = f"**Text Comparison**\n\n"
        result += f"**{ref1}** ({version1}):\n{text1}\n\n"
        result += f"**{ref2}** ({version2}):\n{text2}\n\n"
        
        # Check if there's a comparison note in the database
        book1, cv1 = _parse_reference(ref1)
        ch1, vs1, ve1 = _parse_chap_verse(cv1)
        notes = db.execute(
            "SELECT note FROM comparison_notes WHERE book=? AND chapter=? AND verse_num=?",
            (book1, ch1, vs1)
        ).fetchone()
        if notes:
            result += f"**Scholarly notes**: {notes['note']}\n"
        
        return result
    finally:
        db.close()


# --- Versification normalization (RVR60/English as canonical input) ---

# Maps: (book_lower, english_chapter, english_verse) -> (hebrew_chapter, hebrew_verse)
# Only for cases where Hebrew differs from English/RVR numbering
_VERSE_MAP_TO_HEBREW = {
    # Joel: English 3 chapters, Hebrew 4
    # English Joel 2:28-32 = Hebrew Joel 3:1-5
    # English Joel 3:1-21 = Hebrew Joel 4:1-21
    "joel": {
        (2, v): (3, v - 27) for v in range(28, 33)  # 2:28-32 -> 3:1-5
    } | {
        (3, v): (4, v) for v in range(1, 22)  # 3:1-21 -> 4:1-21
    },
    # Malachi: English 4 chapters, Hebrew 3
    # English Mal 4:1-6 = Hebrew Mal 3:19-24
    "malachi": {
        (4, v): (3, v + 18) for v in range(1, 7)  # 4:1-6 -> 3:19-24
    },
    # Exodus: English 8:1-4 = Hebrew 7:26-29; English 8:5-32 = Hebrew 8:1-28
    "exodus": {
        (8, v): (7, v + 25) for v in range(1, 5)  # 8:1-4 -> 7:26-29
    } | {
        (8, v): (8, v - 4) for v in range(5, 33)  # 8:5-32 -> 8:1-28
    },
    # Numbers: English 16:36-50 = Hebrew 17:1-15
    "numbers": {
        (16, v): (17, v - 35) for v in range(36, 51)  # 16:36-50 -> 17:1-15
    },
    # 1 Samuel: English 21:1-15 = Hebrew 21:2-16 (offset +1 in Hebrew)
    # English 24:1-22 = Hebrew 24:2-23
    # 2 Chronicles: English 2:1-18 = Hebrew 1:18 + 2:1-17
    "2 chronicles": {
        (2, 1): (1, 18),  # 2:1 -> 1:18
    } | {
        (2, v): (2, v - 1) for v in range(2, 19)  # 2:2-18 -> 2:1-17
    },
}

# Reverse: for LXX/Vulgate Psalm numbering
def _psalm_hebrew_to_lxx(ps_num: int) -> tuple[int, str]:
    """Convert Hebrew/RVR Psalm number to LXX/Vulgate number. Returns (lxx_num, note)."""
    if ps_num <= 8:
        return ps_num, ""
    elif ps_num == 9:
        return 9, "LXX combines Ps 9-10 into Ps 9"
    elif ps_num == 10:
        return 9, "LXX combines Ps 9-10 into Ps 9"
    elif 11 <= ps_num <= 113:
        return ps_num - 1, f"LXX/Vulgate: Ps {ps_num - 1}"
    elif ps_num == 114:
        return 113, "LXX combines Ps 114-115 into Ps 113"
    elif ps_num == 115:
        return 113, "LXX combines Ps 114-115 into Ps 113"
    elif 116 <= ps_num <= 145:
        return ps_num - 2, f"LXX/Vulgate: Ps {ps_num - 2}"
    elif ps_num == 146:
        return 146, "LXX combines Ps 146-147 into Ps 146"
    elif ps_num == 147:
        return 146, "LXX combines Ps 146-147 into Ps 146"
    else:
        return ps_num, ""


def _get_versification_note(book: str, chapter: int, verse_start: int, version: str) -> str:
    """Return a note about versification differences if applicable."""
    book_lower = book.lower()
    notes = []
    
    if "psalm" in book_lower or book in ("Ps", "Pss"):
        lxx_num, note = _psalm_hebrew_to_lxx(chapter)
        if note:
            notes.append(f"⚠️ Numeración: RVR Salmo {chapter} = {note}")
    
    # Check if this verse has a Hebrew offset
    for key in _VERSE_MAP_TO_HEBREW:
        if key in book_lower:
            mapping = _VERSE_MAP_TO_HEBREW[key]
            if (chapter, verse_start) in mapping:
                heb_ch, heb_vs = mapping[(chapter, verse_start)]
                notes.append(f"⚠️ Numeración hebrea: {book} {heb_ch}:{heb_vs}")
                break
            # Check chapter-level differences
            if any(ch == chapter for (ch, _) in mapping.keys()):
                sample = next(((ch, v) for (ch, v) in mapping.keys() if ch == chapter), None)
                if sample:
                    heb_ch, _ = mapping[sample]
                    if heb_ch != chapter:
                        notes.append(f"⚠️ Numeración hebrea: este pasaje corresponde a {book} cap. {heb_ch} en el texto hebreo")
                        break
    
    if ("psalm" in book_lower or book == "Ps") and version in ("WLC", "LXX"):
        notes.append("Nota: En el texto hebreo, el título/superscripción cuenta como v.1")
    
    return " | ".join(notes) if notes else ""


def _adjust_chapter_for_version(book: str, chapter: int, verse_start: int, version: str) -> tuple[int, int]:
    """Adjust chapter/verse when querying versions with different numbering. Returns (adjusted_chapter, adjusted_verse)."""
    book_lower = book.lower()
    
    # LXX/Vulgate Psalm adjustment
    if ("psalm" in book_lower or book in ("Ps", "Pss")) and version in ("LXX", "Vulgate"):
        lxx_num, _ = _psalm_hebrew_to_lxx(chapter)
        return lxx_num, verse_start
    
    # WLC Hebrew adjustment (English -> Hebrew)
    if version == "WLC":
        for key in _VERSE_MAP_TO_HEBREW:
            if key in book_lower:
                mapping = _VERSE_MAP_TO_HEBREW[key]
                if (chapter, verse_start) in mapping:
                    return mapping[(chapter, verse_start)]
    
    return chapter, verse_start


# --- Book name normalization ---

_BOOK_ALIASES = {
    # English full -> abbreviations used in WLC/LXX
    "genesis": ["Gen", "Genesis"], "exodus": ["Exod", "Exodus"], "leviticus": ["Lev", "Leviticus"],
    "numbers": ["Num", "Numbers"], "deuteronomy": ["Deut", "Deuteronomy"],
    "joshua": ["Josh", "Joshua"], "judges": ["Judg", "Judges"], "ruth": ["Ruth"],
    "1 samuel": ["1Sam", "1 Samuel", "I Samuel"], "2 samuel": ["2Sam", "2 Samuel", "II Samuel"],
    "1 kings": ["1Kgs", "1 Kings", "I Kings"], "2 kings": ["2Kgs", "2 Kings", "II Kings"],
    "1 chronicles": ["1Chr", "1 Chronicles", "I Chronicles"], "2 chronicles": ["2Chr", "2 Chronicles", "II Chronicles"],
    "ezra": ["Ezra"], "nehemiah": ["Neh", "Nehemiah"], "esther": ["Esth", "Esther"],
    "job": ["Job"], "psalms": ["Ps", "Pss", "Psalms"], "proverbs": ["Prov", "Proverbs"],
    "ecclesiastes": ["Eccl", "Ecclesiastes"], "song of solomon": ["Song", "Song of Solomon"],
    "isaiah": ["Isa", "Isaiah"], "jeremiah": ["Jer", "Jeremiah"],
    "lamentations": ["Lam", "Lamentations"], "ezekiel": ["Ezek", "Ezekiel"],
    "daniel": ["Dan", "Daniel"], "hosea": ["Hos", "Hosea"], "joel": ["Joel"],
    "amos": ["Amos"], "obadiah": ["Obad", "Obadiah"], "jonah": ["Jonah"],
    "micah": ["Mic", "Micah"], "nahum": ["Nah", "Nahum"], "habakkuk": ["Hab", "Habakkuk"],
    "zephaniah": ["Zeph", "Zephaniah"], "haggai": ["Hag", "Haggai"],
    "zechariah": ["Zech", "Zechariah"], "malachi": ["Mal", "Malachi"],
    "matthew": ["Matt", "Matthew"], "mark": ["Mark"], "luke": ["Luke"], "john": ["John"],
    "acts": ["Acts"], "romans": ["Rom", "Romans"],
    "1 corinthians": ["1Cor", "1 Corinthians", "I Corinthians"], "2 corinthians": ["2Cor", "2 Corinthians", "II Corinthians"],
    "galatians": ["Gal", "Galatians"], "ephesians": ["Eph", "Ephesians"],
    "philippians": ["Phil", "Philippians"], "colossians": ["Col", "Colossians"],
    "1 thessalonians": ["1Thess", "1 Thessalonians", "I Thessalonians"], "2 thessalonians": ["2Thess", "2 Thessalonians", "II Thessalonians"],
    "1 timothy": ["1Tim", "1 Timothy", "I Timothy"], "2 timothy": ["2Tim", "2 Timothy", "II Timothy"],
    "titus": ["Titus"], "philemon": ["Phlm", "Philemon"], "hebrews": ["Heb", "Hebrews"],
    "james": ["Jas", "James"], "1 peter": ["1Pet", "1 Peter", "I Peter"], "2 peter": ["2Pet", "2 Peter", "II Peter"],
    "1 john": ["1John", "1 John", "I John"], "2 john": ["2John", "2 John", "II John"], "3 john": ["3John", "3 John", "III John"],
    "jude": ["Jude"], "revelation": ["Rev", "Revelation", "Revelation of John"],
    # Deuterocanonical
    "tobit": ["Tob", "Tobit"], "judith": ["Jdt", "Judith"],
    "wisdom": ["Wis", "Wisdom", "Wisdom of Solomon"],
    "sirach": ["Sir", "Sirach", "Ecclesiasticus"],
    "baruch": ["Bar", "Baruch"], "1 maccabees": ["1Macc", "1 Maccabees"],
    "2 maccabees": ["2Macc", "2 Maccabees"], "3 maccabees": ["3Macc", "3 Maccabees"],
    "4 maccabees": ["4Macc", "4 Maccabees"],
}

def _normalize_book(book: str, version: str) -> str:
    """Find the correct book name for a given version."""
    key = book.lower().strip()
    aliases = _BOOK_ALIASES.get(key, [book])
    # The input itself is always a valid candidate
    candidates = [book] + aliases
    return candidates


def _query_verse(db, book: str, chapter: int, verse_start: int, verse_end: int, version: str):
    """Query verses trying multiple book name variants, adjusting versification."""
    adj_chapter, adj_verse_start = _adjust_chapter_for_version(book, chapter, verse_start, version)
    # Adjust verse_end by same offset
    verse_offset = adj_verse_start - verse_start
    adj_verse_end = verse_end + verse_offset
    
    candidates = _normalize_book(book, version)
    for b in candidates:
        rows = db.execute(
            "SELECT verse_num, text, morphology FROM verses "
            "WHERE book=? AND chapter=? AND verse_num BETWEEN ? AND ? AND version=? "
            "ORDER BY verse_num",
            (b, adj_chapter, adj_verse_start, adj_verse_end, version)
        ).fetchall()
        if rows:
            return rows
    # Fallback: try original chapter/verse (in case adjustment was wrong)
    if adj_chapter != chapter or adj_verse_start != verse_start:
        for b in candidates:
            rows = db.execute(
                "SELECT verse_num, text, morphology FROM verses "
                "WHERE book=? AND chapter=? AND verse_num BETWEEN ? AND ? AND version=? "
                "ORDER BY verse_num",
                (b, chapter, verse_start, verse_end, version)
            ).fetchall()
            if rows:
                return rows
    return []


# --- Helper functions ---

def _parse_reference(ref: str) -> tuple[str, str]:
    """Parse 'John 3:16' into ('John', '3:16') or '1 Cor 15:3-5' into ('1 Cor', '15:3-5')."""
    parts = ref.strip().rsplit(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], "1:1"


def _parse_chap_verse(cv: str) -> tuple[int, int, int]:
    """Parse '3:16' into (3, 16, 16) or '3:16-18' into (3, 16, 18)."""
    if ":" not in cv:
        return int(cv), 1, 176  # whole chapter
    chap, verses = cv.split(":")
    if "-" in verses:
        start, end = verses.split("-")
        return int(chap), int(start), int(end)
    return int(chap), int(verses), int(verses)


def _get_verse_text(db, ref: str, version: str) -> str:
    book, cv = _parse_reference(ref)
    chapter, vs, ve = _parse_chap_verse(cv)
    rows = _query_verse(db, book, chapter, vs, ve, version)
    return " ".join(r['text'] for r in rows) if rows else "(not available)"


def _list_versions(db) -> str:
    rows = db.execute("SELECT DISTINCT version FROM verses").fetchall()
    return ", ".join(r['version'] for r in rows)


def _list_texts(db) -> str:
    rows = db.execute("SELECT name FROM authenticity ORDER BY name").fetchall()
    return ", ".join(r['name'] for r in rows)


def _scope_to_sql(scope: str) -> str:
    mapping = {
        "ot": "WHERE v.canon_status='protocanonical' AND v.testament='OT'",
        "nt": "WHERE v.canon_status='protocanonical' AND v.testament='NT'",
        "deuterocanonical": "WHERE v.canon_status='deuterocanonical'",
        "pseudepigrapha": "WHERE v.canon_status='pseudepigraphal'",
        "dss": "WHERE v.canon_status='dss'",
        "apocryphal": "WHERE v.canon_status='nt_apocryphal'",
        "apostolic_fathers": "WHERE v.canon_status='apostolic_fathers'",
    }
    return mapping.get(scope, "")


def _fts_search(db, query: str, scope: str, limit: int) -> str:
    """Fallback full-text search when embeddings aren't available."""
    scope_filter = _scope_to_sql(scope).replace("WHERE", "AND") if scope != "all" else ""
    rows = db.execute(f"""
        SELECT v.book, v.chapter, v.verse_num, v.version, v.text, v.canon_status
        FROM verses v
        JOIN verses_fts fts ON v.id = fts.rowid
        WHERE verses_fts MATCH ? {scope_filter}
        LIMIT ?
    """, (query, limit)).fetchall()
    
    result = f"**Text search**: \"{query}\" (scope: {scope})\n\n"
    for i, r in enumerate(rows, 1):
        result += f"{i}. [{r['book']} {r['chapter']}:{r['verse_num']}] ({r['version']}) — {r['text'][:200]}\n"
        result += f"   Canon: {r['canon_status']}\n\n"
    return result or "No results found."


_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return _embedding_model


if __name__ == "__main__":
    mcp.run(transport="stdio")
