"""Batch-generate glosses for MorphGNT lemmas not found in the lexicon.

Uses Bedrock Claude to translate Greek lemmas in batches.
Creates/populates the lemma_gloss table.
"""
import sqlite3, unicodedata, re, json, time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"
BATCH_SIZE = 150


def get_unmatched_lemmas(db):
    """Find MorphGNT lemmas that don't match any lexicon entry."""
    rows = db.execute("SELECT DISTINCT lemma FROM morphology WHERE version='MorphGNT' AND lemma != ''").fetchall()
    lemmas = [r[0] for r in rows]

    all_lex = db.execute("SELECT strongs, lemma, lemma_normalized, gloss FROM lexicon").fetchall()
    norm_lex = set()
    stripped_lex = set()
    for lx in all_lex:
        norm_lex.add(unicodedata.normalize('NFC', lx[1]))
        norm_lex.add(lx[1])
        if lx[2]:
            norm_lex.add(unicodedata.normalize('NFC', lx[2]))
        stripped = ''.join(c for c in unicodedata.normalize('NFD', lx[1]) if unicodedata.category(c) != 'Mn').lower()
        stripped_lex.add(stripped)

    # Also exclude already-glossed lemmas
    existing = set()
    try:
        rows2 = db.execute("SELECT lemma FROM lemma_gloss").fetchall()
        existing = {r[0] for r in rows2}
    except Exception:
        pass

    unmatched = []
    for lem in lemmas:
        if lem in existing:
            continue
        clean = re.sub(r'[,.\;·]$', '', lem)
        clean = re.sub(r'\(.\)$', '', clean)
        nfc_clean = unicodedata.normalize('NFC', clean)
        if nfc_clean in norm_lex:
            continue
        stripped = ''.join(c for c in unicodedata.normalize('NFD', clean) if unicodedata.category(c) != 'Mn').lower()
        if stripped in stripped_lex:
            continue
        # Stem match
        found = False
        for trim in range(1, 6):
            if len(stripped) <= trim + 2:
                break
            stem = stripped[:-trim]
            if any(k.startswith(stem) and len(k) <= len(stripped) + 3 for k in stripped_lex):
                found = True
                break
        if not found:
            unmatched.append(lem)
    return unmatched


def batch_gloss(lemmas_batch):
    """Use Bedrock to generate glosses for a batch of Greek lemmas."""
    import boto3
    client = boto3.client("bedrock-runtime", region_name="us-east-1")

    prompt = f"""Give me a brief English gloss (1-5 words) for each of these Greek NT words/forms.
Return ONLY a JSON array of objects with "lemma" and "gloss" keys. No explanation.

Words:
{json.dumps(lemmas_batch, ensure_ascii=False)}"""

    r = client.converse(
        modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 4000, "temperature": 0},
    )
    text = r['output']['message']['content'][0]['text']
    # Extract JSON from response
    start = text.find('[')
    end = text.rfind(']') + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return []


def main():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS lemma_gloss (
        lemma TEXT PRIMARY KEY,
        gloss TEXT NOT NULL
    )""")
    db.commit()

    unmatched = get_unmatched_lemmas(db)
    print(f"Unmatched lemmas to process: {len(unmatched)}", flush=True)

    total_inserted = 0
    for i in range(0, len(unmatched), BATCH_SIZE):
        batch = unmatched[i:i+BATCH_SIZE]
        print(f"  Processing batch {i//BATCH_SIZE + 1} ({len(batch)} lemmas)...", flush=True)
        try:
            results = batch_gloss(batch)
            for item in results:
                if item.get("lemma") and item.get("gloss"):
                    db.execute("INSERT OR IGNORE INTO lemma_gloss (lemma, gloss) VALUES (?, ?)",
                               (item["lemma"], item["gloss"]))
                    total_inserted += 1
            db.commit()
            print(f"    Inserted {len(results)} glosses", flush=True)
        except Exception as e:
            print(f"    Error: {e}", flush=True)
        time.sleep(1)  # Rate limiting

    print(f"\nDone. Total new glosses: {total_inserted}", flush=True)
    db.close()


if __name__ == "__main__":
    main()
