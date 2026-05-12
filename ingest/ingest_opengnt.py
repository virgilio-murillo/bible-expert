"""Ingest OpenGNT word-level data into the morphology table.

Replaces existing MorphGNT entries with richer data including:
- Proper dictionary lemma
- Full RMAC parsing code
- Strong's number
- English gloss (TBESG)
- Spanish gloss

Also creates an rmac_codes table for parsing descriptions.

Source: https://github.com/eliranwong/OpenGNT
"""
import re, sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"
OPENGNT_CSV = Path("/tmp/OpenGNT_version3_3.csv")
RMAC_TSV = Path("/tmp/rmac_english.tsv")

# OpenGNT uses numeric book IDs; map to our book names
BOOK_MAP = {
    40: "Matthew", 41: "Mark", 42: "Luke", 43: "John", 44: "Acts",
    45: "Romans", 46: "1 Corinthians", 47: "2 Corinthians", 48: "Galatians",
    49: "Ephesians", 50: "Philippians", 51: "Colossians", 52: "1 Thessalonians",
    53: "2 Thessalonians", 54: "1 Timothy", 55: "2 Timothy", 56: "Titus",
    57: "Philemon", 58: "Hebrews", 59: "James", 60: "1 Peter", 61: "2 Peter",
    62: "1 John", 63: "2 John", 64: "3 John", 65: "Jude", 66: "Revelation"
}


def ingest_rmac(db):
    """Ingest RMAC parsing code descriptions."""
    db.execute("CREATE TABLE IF NOT EXISTS rmac_codes (code TEXT PRIMARY KEY, description TEXT)")
    db.execute("DELETE FROM rmac_codes")
    with open(RMAC_TSV, encoding="utf-8") as f:
        next(f)  # skip header
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                db.execute("INSERT OR IGNORE INTO rmac_codes (code, description) VALUES (?, ?)",
                           (parts[0], parts[1]))
    db.commit()
    print("RMAC codes ingested.", flush=True)


def ingest_opengnt(db):
    """Replace MorphGNT data with OpenGNT enriched data."""
    # Delete existing MorphGNT entries
    db.execute("DELETE FROM morphology WHERE version='MorphGNT'")

    # Check if gloss_es column exists, add if not
    cols = [r[1] for r in db.execute("PRAGMA table_info(morphology)").fetchall()]
    if "gloss_es" not in cols:
        db.execute("ALTER TABLE morphology ADD COLUMN gloss_es TEXT DEFAULT ''")

    batch = []
    count = 0
    with open(OPENGNT_CSV, encoding="utf-8") as f:
        next(f)  # skip header
        for line in f:
            cols = line.strip().split('\t')
            if len(cols) < 11:
                continue

            # Parse fields
            ref_match = re.findall(r'〔(.+?)〕', cols[6])
            morph_match = re.findall(r'〔(.+?)〕', cols[7])
            gloss_match = re.findall(r'〔(.+?)〕', cols[10])
            if not ref_match or not morph_match or not gloss_match:
                continue

            ref = ref_match[0].split('｜')
            morph = morph_match[0].split('｜')
            glosses = gloss_match[0].split('｜')

            book_num = int(ref[0])
            if book_num not in BOOK_MAP:
                continue

            book = BOOK_MAP[book_num]
            chapter = int(ref[1])
            verse = int(ref[2])
            word = morph[1] if len(morph) > 1 else ""  # OGNTu (unicode)
            lexeme = morph[3] if len(morph) > 3 else ""
            rmac = morph[4] if len(morph) > 4 else ""
            strongs = morph[5] if len(morph) > 5 else ""
            gloss_en = glosses[0] if len(glosses) > 0 else ""
            gloss_es = glosses[4] if len(glosses) > 4 else ""

            count += 1
            batch.append((book, chapter, verse, count, word, lexeme, rmac, gloss_en, strongs, "MorphGNT", gloss_es))

            if len(batch) >= 5000:
                db.executemany(
                    "INSERT INTO morphology (book, chapter, verse_num, word_pos, word, lemma, morph_code, gloss, strongs, version, gloss_es) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    batch)
                batch = []
                print(f"  {count} words...", flush=True)

    if batch:
        db.executemany(
            "INSERT INTO morphology (book, chapter, verse_num, word_pos, word, lemma, morph_code, gloss, strongs, version, gloss_es) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            batch)

    db.commit()
    print(f"Done. Ingested {count} words from OpenGNT.", flush=True)


def main():
    if not OPENGNT_CSV.exists():
        print(f"ERROR: {OPENGNT_CSV} not found. Download first:")
        print("  curl -sL https://raw.githubusercontent.com/eliranwong/OpenGNT/master/OpenGNT_BASE_TEXT.zip -o /tmp/opengnt_base.zip")
        print("  cd /tmp && unzip -o opengnt_base.zip")
        return

    db = sqlite3.connect(str(DB_PATH))
    ingest_rmac(db)
    ingest_opengnt(db)
    db.close()


if __name__ == "__main__":
    main()
