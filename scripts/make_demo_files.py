import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = [json.loads(x) for x in (ROOT / "data" / "test.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()]
yes = [r for r in rows if r["analysis"]["follow_up_needed"]][:2]
no = [r for r in rows if not r["analysis"]["follow_up_needed"]][:1]
out = ROOT / "sample_data"
out.mkdir(exist_ok=True)
for n, r in enumerate(yes + no, 1):
    (out / f"demo_{n}.txt").write_text(r["transcript"], encoding="utf-8")
    a = r["analysis"]
    print(f"demo_{n}.txt: {len(a['action_items'])} action items expected, follow-up = {a['follow_up_needed']}")