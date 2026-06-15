"""Bible Expert MCP Server — Comprehensive biblical research tools."""
import json
import os
import sqlite3
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from books import resolve_book, get_all_db_names, BOOKS

DB_PATH = Path(__file__).parent / "db" / "bible.db"
DATA_DIR = Path(__file__).parent / "data"

# OT book IDs: 1-39 in BOOKS dict
_OT_NAMES = frozenset(BOOKS[i][0] for i in range(1, 40))

def _is_ot(book: str) -> bool:
    """Return True if resolved book name is Old Testament."""
    return book in _OT_NAMES

mcp = FastMCP("Bible-Expert")


def _resolve_book_or_error(book) -> str:
    """Resolve book name/ID or raise a helpful error."""
    resolved = resolve_book(book)
    if resolved:
        return resolved
    # Build hint
    raise ValueError(
        f"Unknown book: '{book}'. Use a numeric ID (1-84), English name, Spanish name, or abbreviation. "
        f"Examples: 2 or 'Exodus' or 'Éxodo' or 'Exod' or 'Ex'"
    )


def get_db(readonly=True):
    """Get a database connection with concurrency-safe settings."""
    if readonly:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=30)
    else:
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@mcp.tool()
def book_list() -> str:
    """List all available book IDs with their canonical names. Use these IDs in other tools."""
    lines = []
    for bid, (name, aliases) in BOOKS.items():
        lines.append(f"{bid}: {name}")
    return "\n".join(lines)


@mcp.tool()
def verse_lookup(book: str, chapter: int, verse_start: int = 1, verse_end: int | None = None, version: str = "SBLGNT", include_morphology: bool = False) -> str:
    """Look up Bible verse(s). Uses RVR60/Hebrew numbering.
    
    Args:
        book: Book name (English/Spanish/abbreviation) or numeric ID (1=Genesis, 2=Exodus... 66=Revelation). Full list via book_list tool.
        chapter: Chapter number
        verse_start: Starting verse (default 1)
        verse_end: Ending verse (default = verse_start, or end of chapter if verse_start=1)
        version: Text version. Options: MorphGNT, LXX, WLC, RVR60, YLT, Vulgate, ApostolicFathers
        include_morphology: Include word-level morphological parsing (Greek/Hebrew only)
    """
    db = get_db()
    try:
        resolved = _resolve_book_or_error(book)
        if verse_end is None:
            verse_end = 176 if verse_start == 1 else verse_start
        
        rows = _query_verse(db, resolved, chapter, verse_start, verse_end, version)
        
        if not rows:
            return f"No results for {resolved} {chapter}:{verse_start}-{verse_end} in {version}. Available versions: " + _list_versions(db)
        
        ref = f"{resolved} {chapter}:{verse_start}" + (f"-{verse_end}" if verse_end != verse_start else "")
        result = f"**{ref}** ({version}):\n\n"
        
        note = _get_versification_note(resolved, chapter, verse_start, version)
        if note:
            result += f"_{note}_\n\n"
        
        for r in rows:
            result += f"  {r['verse_num']}. {r['text']}\n"
            if include_morphology and r['morphology']:
                result += f"     Morphology: {r['morphology']}\n"
        return result
    except ValueError as e:
        return str(e)
    finally:
        db.close()


@mcp.tool()
def parallel_versions(book: str, chapter: int, verse_start: int = 1, verse_end: int | None = None, versions: list[str] | None = None) -> str:
    """Show a verse in multiple translations side-by-side. Uses RVR60/Hebrew numbering as canonical.
    
    Args:
        book: Book name or numeric ID (1-84)
        chapter: Chapter number
        verse_start: Starting verse
        verse_end: Ending verse (default = verse_start)
        versions: List of versions to compare. Default: MorphGNT, LXX, WLC, RVR60, YLT, Vulgate
    """
    if versions is None:
        versions = ["MorphGNT", "LXX", "WLC", "RVR60", "KJV", "BSB", "YLT", "Vulgate"]
    
    db = get_db()
    try:
        resolved = _resolve_book_or_error(book)
        if verse_end is None:
            verse_end = verse_start
        
        ref = f"{resolved} {chapter}:{verse_start}" + (f"-{verse_end}" if verse_end != verse_start else "")
        result = f"**{ref}** — Parallel Comparison:\n"
        
        note = _get_versification_note(resolved, chapter, verse_start, "LXX")
        if note:
            result += f"\n_{note}_\n"
        
        result += "\n"
        for ver in versions:
            rows = _query_verse(db, resolved, chapter, verse_start, verse_end, ver)
            text = " ".join(r['text'] for r in rows) if rows else "(not available)"
            result += f"**{ver}**: {text}\n\n"
        return result
    except ValueError as e:
        return str(e)
    finally:
        db.close()


@mcp.tool()
def semantic_search(query: str, scope: str = "all", limit: int = 10, language: str = "auto") -> str:
    """Search biblical texts by meaning using semantic similarity.
    
    Args:
        query: Natural language query in any language (Spanish, English, Greek, Hebrew, Latin)
        scope: Filter scope. Options: all, ot, nt, deuterocanonical, pseudepigrapha, dss, apocryphal, apostolic_fathers
        limit: Max results to return (default 10)
        language: Which embedding table to search. Options: auto, greek, latin, hebrew, spanish, english. Auto detects from query.
    """
    db = get_db()
    try:
        try:
            import sqlite_vec
            from sentence_transformers import SentenceTransformer
            
            db.enable_load_extension(True)
            sqlite_vec.load(db)
            
            model = _get_embedding_model()
            embedding = model.encode(query)
            
            # Auto-detect language or use specified
            if language == "auto":
                # Check for Greek/Hebrew/Latin characters
                if any(0x0370 <= ord(c) <= 0x03FF or 0x1F00 <= ord(c) <= 0x1FFF for c in query):
                    language = "greek"
                elif any(0x0590 <= ord(c) <= 0x05FF for c in query):
                    language = "hebrew"
                elif all(ord(c) < 0x0250 for c in query if c.isalpha()) and any(w in query.lower() for w in ['et','in','ad','cum','qui','est','deus','dominus']):
                    language = "latin"
                elif any(w in query.lower() for w in ['el','la','los','las','de','en','que','por','con','dios']):
                    language = "spanish"
                else:
                    language = "english"
            
            table = f"verse_embeddings_{language}"
            
            # Check table exists
            exists = db.execute(f"SELECT count(*) FROM sqlite_master WHERE name='{table}'").fetchone()[0]
            if not exists:
                table = "verse_embeddings_spanish"  # fallback
            
            rows = db.execute(f"""
                SELECT v.book, v.chapter, v.verse_num, v.version, v.text, v.canon_status, e.distance
                FROM {table} e
                JOIN verses v ON e.verse_id = v.id
                WHERE e.embedding MATCH ? AND k = ?
            """, (embedding.tobytes(), limit)).fetchall()
            
            result = f"**Semantic search**: \"{query}\" (language: {language})\n\n"
            for i, r in enumerate(rows, 1):
                result += f"{i}. [{r[0]} {r[1]}:{r[2]}] ({r[3]}) — {r[4][:200]}\n"
                result += f"   Canon: {r[5] or 'N/A'} | Distance: {r[6]:.4f}\n\n"
            return result if rows else "No results found."
        except (ImportError, Exception) as e:
            return _fts_search(db, query, scope, limit)
    finally:
        db.close()


@mcp.tool()
def morphology_analysis(book: str, chapter: int, verse_start: int = 1, verse_end: int | None = None, version: str = "MorphGNT") -> str:
    """Get detailed word-by-word morphological analysis for a verse.
    
    Args:
        book: Book name or numeric ID (1-84)
        chapter: Chapter number
        verse_start: Starting verse
        verse_end: Ending verse (default = verse_start)
        version: Morphological source. Options: MorphGNT (Greek NT), WLC (Hebrew OT), LXX
    """
    db = get_db()
    try:
        resolved = _resolve_book_or_error(book)
        if verse_end is None:
            verse_end = verse_start
        
        candidates = get_all_db_names(resolved)
        rows = []
        for b in candidates:
            rows = db.execute(
                "SELECT word_pos, word, lemma, morph_code, gloss, strongs FROM morphology "
                "WHERE book=? AND chapter=? AND verse_num BETWEEN ? AND ? AND version=? "
                "ORDER BY verse_num, word_pos",
                (b, chapter, verse_start, verse_end, version)
            ).fetchall()
            if rows:
                break
        
        if not rows:
            ref = f"{resolved} {chapter}:{verse_start}"
            return f"No morphological data for {ref} in {version}."
        
        ref = f"{resolved} {chapter}:{verse_start}" + (f"-{verse_end}" if verse_end != verse_start else "")
        result = f"**Morphology: {ref}** ({version}):\n\n"
        result += "| # | Word | Lemma | Parsing | Gloss | Strong's |\n|---|------|-------|---------|-------|----------|\n"
        for r in rows:
            result += f"| {r['word_pos']} | {r['word']} | {r['lemma']} | {r['morph_code']} | {r['gloss'] or ''} | {r['strongs'] or ''} |\n"
        return result
    except ValueError as e:
        return str(e)
    finally:
        db.close()


@mcp.tool()
def critical_apparatus(book: str, chapter: int, verse_start: int = 1, verse_end: int | None = None) -> str:
    """Get textual variants and manuscript evidence for a verse.
    
    Args:
        book: Book name or numeric ID (1-84)
        chapter: Chapter number
        verse_start: Starting verse
        verse_end: Ending verse (default = verse_start)
    """
    db = get_db()
    try:
        resolved = _resolve_book_or_error(book)
        if verse_end is None:
            verse_end = verse_start
        
        rows = db.execute(
            "SELECT verse_num, variant_id, reading, manuscripts, text_type, notes FROM apparatus "
            "WHERE book=? AND chapter=? AND verse_num BETWEEN ? AND ? "
            "ORDER BY verse_num, variant_id",
            (resolved, chapter, verse_start, verse_end)
        ).fetchall()
        
        ref = f"{resolved} {chapter}:{verse_start}" + (f"-{verse_end}" if verse_end != verse_start else "")
        if not rows:
            return f"No apparatus data for {ref}. This verse may have no significant variants in our database."
        
        result = f"**Critical Apparatus: {ref}**\n\n"
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
    except ValueError as e:
        return str(e)
    finally:
        db.close()


@mcp.tool()
def patristic_commentary(book: str, chapter: int, verse_start: int = 1, verse_end: int | None = None, fathers: list[str] | None = None) -> str:
    """Get patristic commentary on a verse from the Church Fathers.
    Shows the original language (Greek/Latin) when available, plus English translation.
    
    Args:
        book: Book name or numeric ID (1-84). Examples: "Exodus", "Éxodo", 2, "Ex"
        chapter: Chapter number
        verse_start: Starting verse (default 1 = whole chapter)
        verse_end: Ending verse (default = verse_start, or end of chapter if verse_start=1)
        fathers: Filter by specific fathers. E.g. ["Chrysostom", "Augustine", "Origen"]. Default: all available.
    """
    db = get_db()
    try:
        resolved = _resolve_book_or_error(book)
        if verse_end is None:
            verse_end = 176 if verse_start == 1 else verse_start
        
        candidates = get_all_db_names(resolved)
        rows = []
        for b in candidates:
            if fathers:
                father_clauses = " OR ".join(["father LIKE ?" for _ in fathers])
                q = f"""SELECT id, father, work, text, text_original, original_lang, date_approx 
                       FROM patristic WHERE book=? AND chapter=? AND verse_num BETWEEN ? AND ?
                       AND ({father_clauses}) ORDER BY (text_original IS NOT NULL) DESC, date_approx LIMIT 20"""
                p = [b, chapter, verse_start, verse_end] + [f"%{f}%" for f in fathers]
            else:
                q = """SELECT id, father, work, text, text_original, original_lang, date_approx 
                       FROM patristic WHERE book=? AND chapter=? AND verse_num BETWEEN ? AND ?
                       ORDER BY (text_original IS NOT NULL) DESC, date_approx LIMIT 20"""
                p = [b, chapter, verse_start, verse_end]
            rows = db.execute(q, p).fetchall()
            if rows:
                break
        
        ref = f"{resolved} {chapter}:{verse_start}" + (f"-{verse_end}" if verse_end != verse_start else "")
        if not rows:
            return f"No patristic commentary found for {ref}."
        
        result = f"**Patristic Commentary: {ref}**\n\n"
        for r in rows:
            lang_tag = f" [{r['original_lang'].upper()}]" if r['original_lang'] else ""
            result += f"### {r['father']}{lang_tag} ({r['date_approx'] or '?'}) [id={r['id']}]\n"
            result += f"*{r['work']}*\n\n"
            
            if r['text_original']:
                result += f"**Original ({r['original_lang']}):**\n{r['text_original'][:800]}\n\n"
                result += f"**English translation:**\n{r['text'][:800]}\n\n"
            else:
                result += f"**English translation:**\n{r['text'][:1000]}\n\n"
                result += f"⚠️ _Original {r['original_lang'] or 'greek/latin'} text not in database (id={r['id']}). Find it via web_search, then call save_patristic_original(patristic_id={r['id']}, text_original=..., original_lang=...) to index it._\n"
            
            result += "\n---\n\n"
        
        return result
    except ValueError as e:
        return str(e)
    finally:
        db.close()


@mcp.tool()
def save_patristic_original(patristic_id: int, text_original: str, original_lang: str = "greek") -> str:
    """Save the original Greek/Latin text for a patristic entry that only has English translation.
    Call this after finding the original text via web search.
    
    Args:
        patristic_id: The ID of the patristic record (from patristic_commentary output)
        text_original: The original Greek or Latin text
        original_lang: Language of the original text: "greek" or "latin"
    """
    db = get_db(readonly=False)
    try:
        row = db.execute("SELECT id, father, work FROM patristic WHERE id=?", (patristic_id,)).fetchone()
        if not row:
            return f"No patristic record with id={patristic_id}."
        db.execute(
            "UPDATE patristic SET text_original=?, original_lang=? WHERE id=?",
            (text_original, original_lang, patristic_id)
        )
        db.commit()
        return f"✅ Saved {original_lang} original for {row['father']} — {row['work']} (id={patristic_id}, {len(text_original)} chars)"
    finally:
        db.close()


@mcp.tool()
def cross_references(book: str, chapter: int, verse_start: int = 1, verse_end: int | None = None, include_intertextual: bool = True) -> str:
    """Get cross-references and intertextual connections for a verse.
    
    Args:
        book: Book name or numeric ID (1-84)
        chapter: Chapter number
        verse_start: Starting verse
        verse_end: Ending verse (default = verse_start)
        include_intertextual: Include connections to pseudepigrapha, DSS, and apocrypha (default true)
    """
    db = get_db()
    try:
        resolved = _resolve_book_or_error(book)
        if verse_end is None:
            verse_end = verse_start
        
        candidates = get_all_db_names(resolved)
        rows = []
        for b in candidates:
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
        
        ref = f"{resolved} {chapter}:{verse_start}" + (f"-{verse_end}" if verse_end != verse_start else "")
        if not rows:
            return f"No cross-references found for {ref}."
        
        result = f"**Cross-References: {ref}**\n\n"
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
    except ValueError as e:
        return str(e)
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
def text_comparison(book1: str, chapter1: int, verse1: int, book2: str, chapter2: int, verse2: int, version1: str = "WLC", version2: str = "LXX") -> str:
    """Compare two parallel passages or the same passage in different textual traditions.
    Useful for MT vs LXX, MT vs DSS, Synoptic parallels, etc.
    
    Args:
        book1: First book name or ID
        chapter1: First chapter
        verse1: First verse
        book2: Second book name or ID
        chapter2: Second chapter
        verse2: Second verse
        version1: Version for first passage (default WLC)
        version2: Version for second passage (default LXX)
    """
    db = get_db()
    try:
        resolved1 = _resolve_book_or_error(book1)
        resolved2 = _resolve_book_or_error(book2)
        
        rows1 = _query_verse(db, resolved1, chapter1, verse1, verse1, version1)
        rows2 = _query_verse(db, resolved2, chapter2, verse2, verse2, version2)
        text1 = " ".join(r['text'] for r in rows1) if rows1 else "(not available)"
        text2 = " ".join(r['text'] for r in rows2) if rows2 else "(not available)"
        
        ref1 = f"{resolved1} {chapter1}:{verse1}"
        ref2 = f"{resolved2} {chapter2}:{verse2}"
        result = f"**Text Comparison**\n\n"
        result += f"**{ref1}** ({version1}):\n{text1}\n\n"
        result += f"**{ref2}** ({version2}):\n{text2}\n\n"
        
        notes = db.execute(
            "SELECT note FROM comparison_notes WHERE book=? AND chapter=? AND verse_num=?",
            (resolved1, chapter1, verse1)
        ).fetchone()
        if notes:
            result += f"**Scholarly notes**: {notes['note']}\n"
        
        return result
    except ValueError as e:
        return str(e)
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


# --- Helper functions ---


def _query_verse(db, book: str, chapter: int, verse_start: int, verse_end: int, version: str):
    """Query verses trying multiple book name variants, adjusting versification."""
    adj_chapter, adj_verse_start = _adjust_chapter_for_version(book, chapter, verse_start, version)
    verse_offset = adj_verse_start - verse_start
    adj_verse_end = verse_end + verse_offset
    
    candidates = get_all_db_names(book)
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

def _list_versions(db) -> str:
    rows = db.execute("SELECT DISTINCT version FROM verses").fetchall()
    return ", ".join(r['version'] for r in rows)


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

import threading as _threading
_embedding_lock = _threading.Lock()

def _get_embedding_model():
    global _embedding_model
    with _embedding_lock:
        if _embedding_model is None:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return _embedding_model


@mcp.tool()
def chapter_study(book: str, chapter: int, version: str = "RVR1909", output_dir: str = "") -> str:
    """Generate a complete interactive HTML study of a Bible chapter.
    
    Produces a standalone HTML with:
    - Full chapter text with clickable verses (popup: original text, LXX, morphology, variants, patristic)
    - High-resolution geographic map (PNG) with places, routes, events
    - Chart of Church Fathers distribution
    - Cross-references with hover preview
    - Event timeline
    
    Args:
        book: Book name or numeric ID (1-84)
        chapter: Chapter number
        version: Text version for display. Options: RVR1909, YLT, Vulgate, LXX, WLC, MorphGNT
        output_dir: Directory to save output. Default: ~/bible-studies/<book>-<chapter>/
    """
    import boto3, json
    from map_generator import generate_chapter_map
    
    db = get_db()
    try:
        resolved = _resolve_book_or_error(book)
        candidates = get_all_db_names(resolved)
        
        # Route to OT or NT generator
        if _is_ot(resolved):
            from study_html_generator_ot import gather_chapter_data, generate_study_html
        else:
            from study_html_generator_nt import gather_chapter_data, generate_study_html
        
        # Gather all data
        chapter_data = gather_chapter_data(resolved, chapter, version, candidates)
        if not chapter_data["verses"]:
            return f"No text found for {resolved} {chapter} in {version}."
        
        # Extract geographic data via LLM
        full_text = "\n".join(f"{v['v']}. {v['text']}" for v in chapter_data["verses"][:40])
        geo_data = _extract_geo_data(resolved, chapter, full_text)
        
        # Output directory
        if not output_dir:
            output_dir = str(Path.home() / "bible-studies" / f"{resolved.replace(' ', '_')}-{chapter}")
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        # Generate map
        if geo_data.get("places"):
            generate_chapter_map(
                places=geo_data["places"], routes=geo_data.get("routes", []),
                events=geo_data.get("events", []),
                title=f"Mapa: {resolved} {chapter}",
                output_path=out_path / "map.png"
            )
        
        # Generate HTML
        html_path = generate_study_html(
            book=resolved, chapter=chapter, version=version,
            chapter_data=chapter_data, geo_data=geo_data, output_dir=out_path
        )
        
        # Open main HTML immediately
        import subprocess
        subprocess.Popen(["open", str(html_path)])
        
        # Generate deep analyses in background and auto-open when ready
        import threading
        def _generate_background_analyses():
            import traceback
            try:
                # Patristic & exegetical: always use programmatic generator (fast, no LLM)
                from analysis_generators import _generate_patristic_analysis, _generate_grounded_exegetical, _strip_md
                # Unified: separate per testament
                if _is_ot(resolved):
                    from unified_html_generator_ot import generate_unified_html
                else:
                    from unified_html_generator_nt import generate_unified_html
                
                # Patristic thematic analysis
                if chapter_data.get("patristic"):
                    patr_html = _generate_patristic_analysis(resolved, chapter, chapter_data["patristic"])
                    if patr_html:
                        patr_path = out_path / "patristic_analysis.html"
                        full = f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>Análisis Patrístico — {resolved} {chapter}</title>
<style>body{{font-family:'Segoe UI',system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:1.5rem;line-height:1.7;color:#212121}}h1{{color:#c62828;border-bottom:3px solid #c62828;padding-bottom:0.5rem}}</style></head>
<body><h1>⚖️ Análisis Temático Patrístico — {resolved} {chapter}</h1>{patr_html}</body></html>'''
                        patr_path.write_text(full, encoding="utf-8")
                        subprocess.Popen(["open", str(patr_path)])
                
                # Exegetical synthesis
                if chapter_data.get("greek_commentaries"):
                    exeg_html = _generate_grounded_exegetical(resolved, chapter, chapter_data["greek_commentaries"], chapter_data.get("morphology", {}))
                    if exeg_html:
                        exeg_path = out_path / "exegetical_analysis.html"
                        full = f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>Análisis Exegético — {resolved} {chapter}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif:wght@400;700&display=swap" rel="stylesheet">
<style>body{{font-family:'Segoe UI',system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:1.5rem;line-height:1.7;color:#212121}}h1{{color:#1a237e;border-bottom:3px solid #1a237e;padding-bottom:0.5rem}}</style></head>
<body><h1>📜 Análisis Exegético — {resolved} {chapter}</h1>{exeg_html}</body></html>'''
                        exeg_path.write_text(full, encoding="utf-8")
                        subprocess.Popen(["open", str(exeg_path)])
            except Exception as e:
                err_path = out_path / "background_error.txt"
                err_path.write_text(traceback.format_exc(), encoding="utf-8")

            # Unified analysis (combines all data into one interactive page)
            try:
                unified_path = generate_unified_html(resolved, chapter, chapter_data, out_path)
                if unified_path and unified_path.exists():
                    subprocess.Popen(["open", str(unified_path)])
            except Exception:
                pass
        
        threading.Thread(target=_generate_background_analyses).start()
        
        return f"✅ Study generated and opened: {html_path}\n\n📋 Patristic & exegetical analyses generating in background (will auto-open when ready)."
    except ValueError as e:
        return str(e)
    finally:
        db.close()


def _extract_geo_data(book: str, chapter: int, text: str) -> dict:
    """Use Haiku to extract places, routes, and events from chapter text."""
    import boto3, json
    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1")
        prompt = f"""Analyze this Bible chapter ({book} {chapter}) and extract geographic information.
Return ONLY valid JSON with this structure:
{{"places": [{{"name": "Jerusalem", "role": "capital"}}], "routes": [{{"from": "Egypt", "to": "Sinai", "label": "Exodus"}}], "events": [{{"place": "Jerusalem", "event": "Temple built"}}]}}

Use English place names. Only include places actually mentioned or clearly implied.

Text:
{text[:3000]}"""

        r = client.converse(
            modelId="global.anthropic.claude-haiku-4-5-20251001-v1:0",
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 1000, "temperature": 0},
        )
        response_text = r['output']['message']['content'][0]['text']
        # Extract JSON
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response_text[start:end])
    except Exception:
        pass
    return {"places": [], "routes": [], "events": []}


if __name__ == "__main__":
    mcp.run(transport="stdio")
