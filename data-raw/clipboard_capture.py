#!/usr/bin/env python3
"""Monitor clipboard and append new content to a file.
Each paste is separated by a newline. Press Ctrl+C to stop."""
import subprocess, time, sys

OUTPUT = sys.argv[1] if len(sys.argv) > 1 else "/Users/murivirg/work/bible/ubs5_apparatus.txt"
last = ""
count = 0

print(f"📋 Monitoring clipboard → {OUTPUT}")
print("   Copy text from Logos. Each new clipboard content will be appended.")
print("   Press Ctrl+C when done.\n")

with open(OUTPUT, "a", encoding="utf-8") as f:
    while True:
        try:
            clip = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
            if clip and clip != last:
                last = clip
                f.write(clip + "\n")
                f.flush()
                count += 1
                lines = clip.count("\n") + 1
                preview = clip[:60].replace("\n", " ")
                print(f"  [{count}] +{lines} lines: {preview}...")
            time.sleep(0.5)
        except KeyboardInterrupt:
            print(f"\n✅ Done. {count} pastes saved to {OUTPUT}")
            break
