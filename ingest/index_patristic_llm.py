"""Index patristic passages by biblical reference using Claude via Bedrock (parallel)."""
import json
import sqlite3
import concurrent.futures
import boto3
import time
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"
MODEL = "us.anthropic.claude-sonnet-4-20250514-v1:0"
REGION = "us-east-1"
BATCH_SIZE = 10  # passages per LLM call
MAX_WORKERS = 5  # parallel Bedrock calls (reduced to avoid throttling)
PROMPT_TEMPLATE = """Given these patristic text passages, identify which Bible verses each one comments on or references. Return ONLY a JSON array where each element has "idx" (0-based index) and "refs" (array of references in format "Book Chapter:Verse").

If a passage doesn't clearly reference any specific Bible verse, return empty refs for that idx.
Only include references the passage actually discusses or comments on, not passing mentions.

Passages:
{passages}

Return JSON array only, no explanation."""


def get_client():
    return boto3.client("bedrock-runtime", region_name=REGION)


def call_bedrock(client, batch):
    """Call Bedrock with a batch of passages, return parsed refs."""
    passages_text = "\n\n".join(
        f"[{i}] Father: {row[1]}\nWork: {row[2]}\nText: {row[3][:600]}"
        for i, row in enumerate(batch)
    )
    
    prompt = PROMPT_TEMPLATE.format(passages=passages_text)
    
    for attempt in range(5):
        try:
            response = client.converse(
                modelId=MODEL,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 2000, "temperature": 0},
            )
            text = response["output"]["message"]["content"][0]["text"]
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            return []
        except Exception as e:
            if "Throttling" in str(e) or "Too many" in str(e):
                wait = 2 ** attempt + 1
                time.sleep(wait)
                continue
            print(f"    Error: {e}", flush=True)
            return []
    return []


def process_batch(args):
    """Process a single batch - called in parallel."""
    batch_idx, batch, client = args
    results = call_bedrock(client, batch)
    
    indexed = []
    if not results:
        return batch_idx, indexed
    
    for item in results:
        if not isinstance(item, dict):
            continue
        idx = item.get("idx", -1)
        refs = item.get("refs", [])
        if not isinstance(refs, list) or idx < 0 or idx >= len(batch):
            continue
        if not refs:
            continue
        row = batch[idx]
        rowid, father, work, text, date_approx, source = row
        for ref in refs:
            # Parse "Book Chapter:Verse"
            parts = ref.rsplit(" ", 1)
            if len(parts) == 2 and ":" in parts[1]:
                book = parts[0]
                cv = parts[1].split(":")
                try:
                    ch, vs = int(cv[0]), int(cv[1].split("-")[0])
                    indexed.append((book, ch, vs, father, work, text[:1500], date_approx, source))
                except ValueError:
                    continue
    return batch_idx, indexed


def main():
    conn = sqlite3.connect(str(DB_PATH))
    
    # Get unindexed passages (those with chapter=0 and substantial text)
    # Skip first 1500 that were already processed in previous run
    rows = conn.execute(
        "SELECT rowid, father, work, text, date_approx, source_collection "
        "FROM patristic WHERE chapter = 0 AND length(text) > 200 "
        "ORDER BY rowid LIMIT -1 OFFSET 1500"
    ).fetchall()
    
    print(f"Passages to index: {len(rows)}", flush=True)
    print(f"Batches of {BATCH_SIZE}: {len(rows) // BATCH_SIZE}", flush=True)
    print(f"Parallel workers: {MAX_WORKERS}", flush=True)
    print(flush=True)
    
    # Create batches
    batches = []
    for i in range(0, len(rows), BATCH_SIZE):
        batches.append(rows[i:i + BATCH_SIZE])
    
    # Process in parallel
    client = get_client()
    total_indexed = 0
    processed = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all batches
        futures = []
        for batch_idx, batch in enumerate(batches):
            futures.append(
                executor.submit(process_batch, (batch_idx, batch, client))
            )
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(futures):
            try:
                batch_idx, indexed = future.result()
                if indexed:
                    conn.executemany(
                        "INSERT OR IGNORE INTO patristic (book, chapter, verse_num, father, work, text, date_approx, source_collection) VALUES (?,?,?,?,?,?,?,?)",
                        indexed
                    )
                    total_indexed += len(indexed)
                
                processed += 1
                if processed % 50 == 0:
                    conn.commit()
                    print(f"  Progress: {processed}/{len(batches)} batches, {total_indexed} refs indexed", flush=True)
            except Exception as e:
                print(f"  Batch failed: {e}", flush=True)
                processed += 1
    
    conn.commit()
    conn.close()
    
    print(f"\nDone! Indexed {total_indexed} new verse references from {len(rows)} passages.", flush=True)


if __name__ == "__main__":
    main()
