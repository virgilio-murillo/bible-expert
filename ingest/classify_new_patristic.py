"""Classify newly ingested patristic passages to specific verses.

Optimized version: processes only target fathers, uses higher distance threshold,
and runs LLM classification in parallel.
"""
import sqlite3, json, time, boto3, sys
import concurrent.futures
from pathlib import Path
from sentence_transformers import SentenceTransformer
import sqlite_vec

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"
MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
TOP_K = 8
DISTANCE_THRESHOLD = 4.5  # slightly more permissive
LLM_BATCH = 30
LLM_WORKERS = 20

TARGET_FATHERS = [
    "Augustine", "Gregory the Great", "John Chrysostom", "Origen", "Jerome",
    "Clement of Alexandria", "Ambrose", "Basil of Caesarea"
]


def run():
    print("Loading embedding model...", flush=True)
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    conn = sqlite3.connect(str(DB_PATH))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)

    placeholders = ",".join(["?"] * len(TARGET_FATHERS))
    rows = conn.execute(f"""
        SELECT rowid, father, text, text_original, original_lang, work, date_approx, source_collection
        FROM patristic WHERE chapter = 0
        AND father IN ({placeholders})
        AND (length(text) > 80 OR length(COALESCE(text_original,'')) > 80)
    """, TARGET_FATHERS).fetchall()
    print(f"Passages to classify: {len(rows):,}", flush=True)

    # Phase 1: Embedding search
    print("\n=== PHASE 1: Similarity Search ===", flush=True)
    candidates = []
    for i, row in enumerate(rows):
        rowid, father, text_en, text_orig, lang, work, date_approx, source = row

        search_text = (text_en or text_orig or '')[:512]
        if len(search_text) < 50:
            continue

        # Search English embeddings (most reliable for our English-translated sources)
        emb = model.encode(search_text)
        try:
            results = conn.execute("""
                SELECT v.book, v.chapter, v.verse_num, e.distance
                FROM verse_embeddings_english e
                JOIN verses v ON e.verse_id = v.id
                WHERE e.embedding MATCH ? AND k = ?
            """, (emb.tobytes(), TOP_K)).fetchall()

            for book, ch, vs, dist in results:
                if dist < DISTANCE_THRESHOLD:
                    candidates.append((rowid, book, ch, vs, dist, father, text_en, text_orig, lang, work, date_approx, source))
        except:
            pass

        if (i + 1) % 500 == 0:
            print(f"  {i+1:,}/{len(rows):,} — {len(candidates):,} candidates", flush=True)

    # Deduplicate
    seen = {}
    for c in candidates:
        key = (c[0], c[1], c[2], c[3])
        if key not in seen or c[4] < seen[key][4]:
            seen[key] = c
    candidates = list(seen.values())
    print(f"\n  Phase 1: {len(candidates):,} unique candidates", flush=True)

    conn.close()

    if not candidates:
        print("No candidates found. Done.", flush=True)
        return

    # Phase 2: LLM classification
    print(f"\n=== PHASE 2: LLM Classification ===", flush=True)
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    conn = sqlite3.connect(str(DB_PATH))

    batches = [candidates[i:i+LLM_BATCH] for i in range(0, len(candidates), LLM_BATCH)]
    print(f"  Batches: {len(batches):,} | Workers: {LLM_WORKERS}", flush=True)

    verified = 0
    processed = 0
    errors = 0

    def classify_batch(batch):
        lines = []
        for i, c in enumerate(batch):
            _, book, ch, vs, dist, father, text_en, text_orig, lang, work, _, _ = c
            snippet = (text_en or text_orig or '')[:300]
            lines.append(f"[{i}] {book} {ch}:{vs} | {father} ({work}) | \"{snippet}\"")

        prompt = (
            "For each entry below, determine if the patristic text ACTUALLY discusses, comments on, "
            "or references the specific Bible verse indicated. Consider direct quotation, exegesis, "
            "allusion, or typological interpretation as valid connections.\n\n"
            + "\n".join(lines)
            + "\n\nReturn ONLY a JSON array of booleans, e.g. [true, false, true, ...]"
        )

        for attempt in range(5):
            try:
                r = client.converse(
                    modelId=MODEL_ID,
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                    inferenceConfig={"maxTokens": 500, "temperature": 0},
                )
                text = r['output']['message']['content'][0]['text']
                s, e = text.find('['), text.rfind(']') + 1
                if s >= 0 and e > s:
                    return json.loads(text[s:e])
                return [False] * len(batch)
            except Exception as ex:
                if "Throttling" in str(ex) or "throttl" in str(ex).lower():
                    time.sleep(2 ** attempt)
                    continue
                return [False] * len(batch)
        return [False] * len(batch)

    with concurrent.futures.ThreadPoolExecutor(max_workers=LLM_WORKERS) as executor:
        futures = {executor.submit(classify_batch, b): b for b in batches}

        for future in concurrent.futures.as_completed(futures):
            batch = futures[future]
            try:
                results = future.result()
                if len(results) != len(batch):
                    results = (results + [False] * len(batch))[:len(batch)]
                for is_valid, c in zip(results, batch):
                    if is_valid:
                        rowid, book, ch, vs, dist, father, text_en, text_orig, lang, work, date_approx, source = c
                        conn.execute("""
                            INSERT OR IGNORE INTO patristic
                            (book, chapter, verse_num, father, work, text, text_original, original_lang, date_approx, source_collection)
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, (book, ch, vs, father, work,
                              (text_en or '')[:1500],
                              (text_orig or '')[:2000],
                              lang or '', date_approx or '', source or ''))
                        verified += 1
            except Exception as ex:
                errors += 1
            processed += 1
            if processed % 20 == 0:
                conn.commit()
                print(f"  {processed}/{len(batches)} batches — {verified:,} verified, {errors} errors", flush=True)

    conn.commit()
    conn.close()
    print(f"\n=== DONE: {verified:,} passages classified to verses ===", flush=True)


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"Total time: {time.time()-t0:.0f}s", flush=True)
