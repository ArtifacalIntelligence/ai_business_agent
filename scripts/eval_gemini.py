import argparse
import difflib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel
from app.llm import SYSTEM_PROMPT
from app.schemas import MeetingAnalysis

load_dotenv(ROOT / ".env")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


class BatchOut(BaseModel):
    analyses: list[MeetingAnalysis]


def ask(chunk):
    parts = [f"=== TRANSCRIPT {i + 1} ===\n{r['transcript']}" for i, r in enumerate(chunk)]
    prompt = (f"Analyze each of the following {len(chunk)} meeting transcripts independently. "
              f"Return exactly {len(chunk)} analyses in the same order.\n\n" + "\n\n".join(parts))
    resp = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, response_mime_type="application/json",
            response_schema=BatchOut, temperature=0.2))
    out = BatchOut.model_validate_json(resp.text).analyses
    if len(out) != len(chunk):
        raise ValueError(f"expected {len(chunk)} analyses, got {len(out)}")
    return [a.model_dump() for a in out]


# ---- same scoring as the Colab notebook ----
def norm(x):
    return (x or "").strip().lower() or None


def sim(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def ddl_match(a, b):
    a, b = norm(a), norm(b)
    if a is None or b is None:
        return a == b
    return a in b or b in a


def score(rows, preds):
    c = dict(valid=0, g_total=0, g_hit=0, p_total=0, p_hit=0,
             own_ok=0, own_n=0, ddl_ok=0, ddl_n=0, fu_ok=0, fu_n=0)
    for row, pred in zip(rows, preds):
        gold = row["analysis"]
        gi = gold["action_items"]
        c["g_total"] += len(gi)
        c["fu_n"] += 1
        if pred is None:
            continue
        c["valid"] += 1
        pi = [i for i in pred["action_items"] if isinstance(i, dict) and i.get("task")]
        c["p_total"] += len(pi)
        c["fu_ok"] += int(pred["follow_up_needed"] == gold["follow_up_needed"])
        for p in pi:
            if any(sim(p["task"], g["task"]) >= 0.5 for g in gi):
                c["p_hit"] += 1
        for g in gi:
            best = max(pi, key=lambda p: sim(p["task"], g["task"]), default=None)
            if best and sim(best["task"], g["task"]) >= 0.5:
                c["g_hit"] += 1
                c["own_n"] += 1
                c["own_ok"] += int(norm(best.get("owner")) == norm(g.get("owner")))
                c["ddl_n"] += 1
                c["ddl_ok"] += int(ddl_match(best.get("deadline"), g.get("deadline")))
    d = lambda a, b: round(a / b, 2) if b else 0.0
    return {
        "json_valid": d(c["valid"], len(rows)),
        "action_recall": d(c["g_hit"], c["g_total"]),
        "action_precision": d(c["p_hit"], c["p_total"]),
        "owner_accuracy": d(c["own_ok"], c["own_n"]),
        "deadline_accuracy": d(c["ddl_ok"], c["ddl_n"]),
        "follow_up_accuracy": d(c["fu_ok"], c["fu_n"]),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-call", type=int, default=5)
    ap.add_argument("--max-calls", type=int, default=8, help="request budget for this run")
    args = ap.parse_args()

    rows = [json.loads(l) for l in (ROOT / "data" / "test.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print(f"Using model: {MODEL} | {len(rows)} test meetings | budget {args.max_calls} requests")

    preds = [None] * len(rows)
    calls, pos, stop = 0, 0, False
    for i in range(0, len(rows), args.per_call):
        chunk = rows[i:i + args.per_call]
        for attempt in range(2):
            if calls >= args.max_calls:
                stop = True
                break
            calls += 1
            try:
                preds[i:i + len(chunk)] = ask(chunk)
                print(f"request {calls}: meetings {i + 1}-{i + len(chunk)} done")
                break
            except Exception as e:
                msg = str(e)
                print(f"request {calls} failed: {msg[:200]}")
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                    stop = True
                    break
                time.sleep(10)
        if stop:
            break
        time.sleep(8)

    missing = sum(p is None for p in preds)
    if missing:
        print(f"WARNING: {missing} of {len(rows)} meetings have no answer and count as invalid.")
    scores = score(rows, preds)

    mpath = ROOT / "model" / "metrics.json"
    mpath.parent.mkdir(exist_ok=True)
    metrics = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    metrics["gemini"] = scores
    metrics["notes"] = {"gemini_model": MODEL, "gemini_batching": f"{args.per_call} meetings per request"}
    mpath.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (ROOT / "model" / "gemini_predictions.json").write_text(json.dumps(preds, indent=2), encoding="utf-8")

    cols = [k for k in ("base", "tuned", "gemini") if isinstance(metrics.get(k), dict)]
    print(f"\n{'metric':22}" + "".join(f"{c:>9}" for c in cols))
    for m in scores:
        print(f"{m:22}" + "".join(f"{metrics[c][m]:>9}" for c in cols))