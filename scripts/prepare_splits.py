import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.llm import SYSTEM_PROMPT

SRC = ROOT / "data" / "dataset.jsonl"
rows, seen = [], set()
for line in SRC.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    key = r["transcript"].strip()[:200]
    if key in seen or len(r["transcript"]) < 200:
        continue  # skip duplicates and tiny transcripts
    seen.add(key)
    rows.append(r)

random.Random(42).shuffle(rows)
n = len(rows)
n_test = max(5, round(n * 0.15))
n_val = max(5, round(n * 0.10))
test, val, train = rows[:n_test], rows[n_test:n_test + n_val], rows[n_test + n_val:]


def chat(r):
    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": r["transcript"]},
        {"role": "assistant", "content": json.dumps(r["analysis"], ensure_ascii=False)},
    ]}


def write(name, items, fmt):
    path = ROOT / "data" / name
    path.write_text("\n".join(json.dumps(fmt(x), ensure_ascii=False) for x in items) + "\n",
                    encoding="utf-8")
    print(f"{name}: {len(items)} examples")


write("train.jsonl", train, chat)
write("val.jsonl", val, chat)
write("test.jsonl", test, lambda r: {"transcript": r["transcript"], "analysis": r["analysis"]})
print(f"usable examples in total: {n}")
if n < 60:
    print("Warning: fewer than 60 usable examples. Generate more before training.")