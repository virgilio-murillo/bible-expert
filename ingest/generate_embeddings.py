"""Generate semantic embeddings for Bible verses using multilingual model."""
import sqlite3
import struct
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 256
# Only embed these versions (most useful for search)
VERSIONS_TO_EMBED = ["RVR1960", "YLT", "MorphGNT", "ApostolicFathers"]


def create_vec_table(conn):
    """Create the vector table using sqlite-vec."""
    import sqlite_vec
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.execute("DROP TABLE IF EXISTS verse_embeddings")
    conn.execute("""
        CREATE VIRTUAL TABLE verse_embeddings USING vec0(
            verse_id INTEGER PRIMARY KEY,
            embedding float[384]
        )
    """)
    conn.commit()


def embed_verses():
    from sentence_transformers import SentenceTransformer
    
    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    
    conn = sqlite3.connect(str(DB_PATH))
    create_vec_table(conn)
    
    # Get verses to embed
    placeholders = ",".join("?" * len(VERSIONS_TO_EMBED))
    total = conn.execute(
        f"SELECT count(*) FROM verses WHERE version IN ({placeholders})",
        VERSIONS_TO_EMBED
    ).fetchone()[0]
    print(f"Embedding {total} verses...")
    
    cursor = conn.execute(
        f"SELECT id, text FROM verses WHERE version IN ({placeholders})",
        VERSIONS_TO_EMBED
    )
    
    batch_ids = []
    batch_texts = []
    embedded = 0
    
    for row in cursor:
        batch_ids.append(row[0])
        batch_texts.append(row[1][:512])  # cap text length
        
        if len(batch_ids) >= BATCH_SIZE:
            embeddings = model.encode(batch_texts, show_progress_bar=False)
            for vid, emb in zip(batch_ids, embeddings):
                conn.execute(
                    "INSERT INTO verse_embeddings (verse_id, embedding) VALUES (?, ?)",
                    (vid, emb.tobytes())
                )
            embedded += len(batch_ids)
            if embedded % 5000 == 0:
                conn.commit()
                print(f"  {embedded}/{total} ({100*embedded//total}%)", flush=True)
            batch_ids = []
            batch_texts = []
    
    # Final batch
    if batch_ids:
        embeddings = model.encode(batch_texts, show_progress_bar=False)
        for vid, emb in zip(batch_ids, embeddings):
            conn.execute(
                "INSERT INTO verse_embeddings (verse_id, embedding) VALUES (?, ?)",
                (vid, emb.tobytes())
            )
        embedded += len(batch_ids)
    
    conn.commit()
    conn.close()
    print(f"Done! {embedded} verses embedded.")


if __name__ == "__main__":
    embed_verses()
