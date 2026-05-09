"""Initialize the Bible Expert SQLite database schema."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        -- Core verses table (all texts, all versions)
        CREATE TABLE IF NOT EXISTS verses (
            id INTEGER PRIMARY KEY,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse_num INTEGER NOT NULL,
            version TEXT NOT NULL,
            text TEXT NOT NULL,
            testament TEXT,          -- OT, NT, null for extra-biblical
            canon_status TEXT,       -- protocanonical, deuterocanonical, pseudepigraphal, nt_apocryphal, apostolic_fathers, dss, expansion
            morphology TEXT,         -- JSON array of word-level data (optional)
            UNIQUE(book, chapter, verse_num, version)
        );
        CREATE INDEX IF NOT EXISTS idx_verses_ref ON verses(book, chapter, verse_num);
        CREATE INDEX IF NOT EXISTS idx_verses_version ON verses(version);
        CREATE INDEX IF NOT EXISTS idx_verses_canon ON verses(canon_status);

        -- FTS5 for full-text search
        CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(
            text, content=verses, content_rowid=id
        );

        -- Morphology word-level data
        CREATE TABLE IF NOT EXISTS morphology (
            id INTEGER PRIMARY KEY,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse_num INTEGER NOT NULL,
            version TEXT NOT NULL,
            word_pos INTEGER NOT NULL,
            word TEXT NOT NULL,
            lemma TEXT,
            morph_code TEXT,
            gloss TEXT,
            strongs TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_morph_ref ON morphology(book, chapter, verse_num, version);
        CREATE INDEX IF NOT EXISTS idx_morph_strongs ON morphology(strongs);

        -- Critical apparatus
        CREATE TABLE IF NOT EXISTS apparatus (
            id INTEGER PRIMARY KEY,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse_num INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            reading TEXT NOT NULL,
            manuscripts TEXT,
            text_type TEXT,          -- Alexandrian, Western, Byzantine, Caesarean
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_apparatus_ref ON apparatus(book, chapter, verse_num);

        -- Patristic commentary indexed by verse
        CREATE TABLE IF NOT EXISTS patristic (
            id INTEGER PRIMARY KEY,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse_num INTEGER NOT NULL,
            father TEXT NOT NULL,
            work TEXT,
            text TEXT NOT NULL,
            date_approx TEXT,
            source_collection TEXT   -- ANF, NPNF1, NPNF2, Catena
        );
        CREATE INDEX IF NOT EXISTS idx_patristic_ref ON patristic(book, chapter, verse_num);
        CREATE INDEX IF NOT EXISTS idx_patristic_father ON patristic(father);

        -- Cross-references
        CREATE TABLE IF NOT EXISTS cross_refs (
            id INTEGER PRIMARY KEY,
            source_book TEXT NOT NULL,
            source_chapter INTEGER NOT NULL,
            source_verse INTEGER NOT NULL,
            target_ref TEXT NOT NULL,
            relationship TEXT,       -- quotation, allusion, parallel, typology, echo
            target_canon_status TEXT,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_xref_source ON cross_refs(source_book, source_chapter, source_verse);

        -- Lexicon (Strong's + Thayer's + BDB)
        CREATE TABLE IF NOT EXISTS lexicon (
            id INTEGER PRIMARY KEY,
            strongs TEXT UNIQUE NOT NULL,
            lemma TEXT NOT NULL,
            gloss TEXT,
            definition TEXT,
            etymology TEXT,
            frequency INTEGER,
            corpus TEXT,             -- NT, OT, LXX
            root TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_lexicon_lemma ON lexicon(lemma);

        -- Authenticity reports
        CREATE TABLE IF NOT EXISTS authenticity (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            alt_names TEXT,
            date_composition TEXT,
            date_consensus TEXT,
            original_language TEXT,
            earliest_manuscripts TEXT,
            patristic_citations TEXT,
            archaeological_evidence TEXT,
            canon_status_detail TEXT,
            scholarly_debates TEXT,
            interpolations TEXT,
            summary TEXT
        );

        -- Dead Sea Scrolls
        CREATE TABLE IF NOT EXISTS dss (
            id INTEGER PRIMARY KEY,
            scroll_id TEXT NOT NULL,
            name TEXT,
            description TEXT,
            col_num INTEGER,
            line_num INTEGER,
            text TEXT,
            translation TEXT,
            parallel_ref TEXT        -- parallel canonical reference if any
        );
        CREATE INDEX IF NOT EXISTS idx_dss_scroll ON dss(scroll_id);

        -- Canon history timeline
        CREATE TABLE IF NOT EXISTS canon_history (
            id INTEGER PRIMARY KEY,
            book TEXT NOT NULL,
            date_event TEXT,
            event TEXT NOT NULL,
            tradition TEXT,          -- Jewish, Catholic, Orthodox, Protestant, Ethiopian, Syriac
            decision TEXT,           -- accepted, rejected, disputed, quoted_as_scripture
            source TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_canon_book ON canon_history(book);

        -- Comparison notes (for text_comparison tool)
        CREATE TABLE IF NOT EXISTS comparison_notes (
            id INTEGER PRIMARY KEY,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse_num INTEGER NOT NULL,
            note TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
