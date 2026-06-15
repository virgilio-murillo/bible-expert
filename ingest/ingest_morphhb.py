"""Ingest Open Scriptures Hebrew Bible (morphhb) word-level morphology into the DB.

Source: https://github.com/openscriptures/morphhb
Format: OSIS XML with <w lemma="1234" morph="H..."> elements per word.

Populates the `morphology` table with version='WLC' for all 39 OT books.
"""
import sqlite3, sys
import xml.etree.ElementTree as ET
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"
MORPHHB_DIR = Path("/tmp/morphhb/wlc")
NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"

# Files map directly to DB book names (they match exactly)
BOOKS = [
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth",
    "1Sam", "2Sam", "1Kgs", "2Kgs", "1Chr", "2Chr", "Ezra", "Neh", "Esth",
    "Job", "Ps", "Prov", "Eccl", "Song", "Isa", "Jer", "Lam",
    "Ezek", "Dan", "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic",
    "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal"
]


def ingest_book(db, book: str):
    """Parse one OSIS XML file and insert word-level morphology."""
    xml_path = MORPHHB_DIR / f"{book}.xml"
    if not xml_path.exists():
        print(f"  SKIP {book} (file not found)", flush=True)
        return 0

    tree = ET.parse(xml_path)
    root = tree.getroot()
    batch = []

    for verse in root.iter(f"{NS}verse"):
        osis_id = verse.get("osisID", "")
        # Format: Book.Chapter.Verse
        parts = osis_id.split(".")
        if len(parts) != 3:
            continue
        chapter, verse_num = int(parts[1]), int(parts[2])

        word_pos = 0
        for w in verse.iter(f"{NS}w"):
            word_pos += 1
            text = w.text or ""
            if not text.strip():
                continue

            lemma_raw = w.get("lemma", "")
            morph = w.get("morph", "")

            # Parse lemma: can be "1234", "1234 a", "c/1234" (prefix/Strong's)
            # Extract the main Strong's number
            strongs = ""
            for part in lemma_raw.replace("/", " ").split():
                if part.isdigit():
                    strongs = f"H{part}"
                    break
                # Handle "1234a" style
                stripped = "".join(c for c in part if c.isdigit())
                if stripped:
                    strongs = f"H{stripped}"
                    break

            batch.append((book, chapter, verse_num, "WLC", word_pos,
                          text, strongs, morph, "", ""))

    if batch:
        db.executemany(
            "INSERT INTO morphology (book, chapter, verse_num, version, word_pos, word, lemma, morph_code, gloss, strongs) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(b, c, v, ver, wp, word, strongs, morph, gloss, strongs2)
             for b, c, v, ver, wp, word, strongs, morph, gloss, strongs2 in batch]
        )
    return len(batch)


def main():
    if not MORPHHB_DIR.exists():
        print(f"ERROR: {MORPHHB_DIR} not found. Run: git clone --depth 1 https://github.com/openscriptures/morphhb.git /tmp/morphhb", flush=True)
        sys.exit(1)

    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")

    # Clear existing WLC morphology
    deleted = db.execute("DELETE FROM morphology WHERE version='WLC'").rowcount
    if deleted:
        print(f"Cleared {deleted} existing WLC rows.", flush=True)

    total = 0
    for book in BOOKS:
        count = ingest_book(db, book)
        total += count
        print(f"  {book}: {count:,} words", flush=True)

    db.commit()
    db.close()
    print(f"\nDone. Inserted {total:,} WLC morphology entries.", flush=True)


if __name__ == "__main__":
    main()
