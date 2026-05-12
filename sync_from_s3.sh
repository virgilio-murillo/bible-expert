#!/bin/bash
# Sync bible study data from S3 to local machine.
# Run this on your Arch Linux laptop to get the latest DB and cache.
# Requires: aws cli configured with access to the account.

S3_BUCKET="bible-study-cache-609009159737"
LOCAL_DB_DIR="${HOME}/.kiro/mcp-servers/bible-tools/db"

echo "Syncing bible.db from S3..."
mkdir -p "$LOCAL_DB_DIR"
aws s3 cp "s3://${S3_BUCKET}/db/bible.db" "$LOCAL_DB_DIR/bible.db"

echo "Done. DB size: $(du -h "$LOCAL_DB_DIR/bible.db" | cut -f1)"
echo ""
echo "The LLM cache is read directly from S3 at runtime."
echo "No additional sync needed for cached analyses."
