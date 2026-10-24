import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel
from app.schemas import MeetingAnalysis

load_dotenv(ROOT / ".env")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


class SyntheticExample(BaseModel):
    transcript: str
    analysis: MeetingAnalysis

class SyntheticBatch(BaseModel):
    examples: list[SyntheticExample]


MEETING_TYPES = [
    "weekly marketing team meeting", "product launch planning", "sprint planning for a software team",
    "sales pipeline review", "budget review with finance", "customer complaint escalation",
    "HR hiring discussion", "project kickoff", "quarterly business review", "website redesign meeting",
    "supply chain delay discussion", "event planning meeting", "IT security incident review",
]
STYLES = [
    "formal and well organized", "casual with interruptions and small talk",
    "short and rushed (about 10 lines)", "long with side discussions (about 40 lines)",
    "no deadlines are mentioned at all", "people disagree before reaching a decision",
    "one action item has no clear owner", "ends with the need for a follow-up meeting",
]
NAMES = ["Ahmed", "Sarah", "Ali", "Fatima", "Omar", "Zainab", "Hassan", "Ayesha", "Bilal", "Mariam"]

# PROMPT = """Write a realistic business meeting transcript, then the correct analysis of it.

PROMPT = """Write {k} DIFFERENT realistic business meeting transcripts, each followed by its correct analysis.

Specs, one per example, in this order:
{specs}

Transcript rules:
- Format each line as "Name: sentence".
- Decisions, action items, owners, deadlines and concerns must be said clearly in the conversation.

Analysis rules:
- Fill each analysis ONLY from facts stated in its own transcript.
- Use null for an owner or deadline that is not stated.
- follow_up_needed is true only if that transcript says another meeting is needed.
- summary: 2-4 sentences."""

# Meeting type: {mtype}
# Style: {style}
# Participants (use 3-5 of these): {names}

# Transcript rules:
# - Format each line as "Name: sentence".
# - Decisions, action items, owners, deadlines and concerns must be said clearly in the conversation.

# Analysis rules:
# - Fill the analysis ONLY from facts stated in your transcript.
# - Use null for an owner or deadline that is not stated.
# - follow_up_needed is true only if the transcript says another meeting is needed.
# - summary: 2-4 sentences."""


# def generate_one(i: int) -> dict:
#     rnd = random.Random(i)
#     prompt = PROMPT.format(
#         mtype=rnd.choice(MEETING_TYPES), style=rnd.choice(STYLES),
#         names=", ".join(rnd.sample(NAMES, 5)),
#     )
#     resp = client.models.generate_content(
#         model=MODEL, contents=prompt,
#         config=types.GenerateContentConfig(
#             response_mime_type="application/json",
#             response_schema=SyntheticExample, temperature=1.0),
#     )
#     ex = SyntheticExample.model_validate_json(resp.text)
#     return {"transcript": ex.transcript, "analysis": ex.analysis.model_dump()}

def generate_batch(start: int, k: int) -> list[dict]:
    rnd = random.Random(start)
    specs = "\n".join(
        f"{j + 1}. Type: {rnd.choice(MEETING_TYPES)}; style: {rnd.choice(STYLES)}; "
        f"participants (use 3-5 of): {', '.join(rnd.sample(NAMES, 5))}"
        for j in range(k)
    )
    resp = client.models.generate_content(
        model=MODEL,
        contents=PROMPT.format(k=k, specs=specs),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SyntheticBatch, temperature=1.0),
    )
    batch = SyntheticBatch.model_validate_json(resp.text)
    return [{"model": MODEL, "transcript": ex.transcript,
             "analysis": ex.analysis.model_dump()} for ex in batch.examples]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100, help="total examples wanted in the file")
    ap.add_argument("--per-call", type=int, default=5)
    ap.add_argument("--max-calls", type=int, default=15,
                    help="stop after this many requests (protects your daily quota)")
    ap.add_argument("--out", default=str(ROOT / "data" / "dataset.jsonl"))
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    done = sum(1 for _ in out.open(encoding="utf-8")) if out.exists() else 0
    print(f"Using model: {MODEL}")
    print(f"{done} examples already saved, target {args.n}")

    calls = failures = 0
    while done < args.n and calls < args.max_calls and failures < 3:
        k = min(args.per_call, args.n - done)
        calls += 1
        try:
            examples = generate_batch(done, k)
            with out.open("a", encoding="utf-8") as f:
                for ex in examples:
                    f.write(json.dumps(ex, ensure_ascii=False) + "\n")
            done += len(examples)
            failures = 0
            print(f"request {calls}/{args.max_calls}: saved, total {done}/{args.n}")
            time.sleep(7)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                print("Daily quota reached for this model. Run again tomorrow, or set another model.")
                break
            failures += 1
            print(f"error ({failures}/3): {msg[:200]}")
            time.sleep(30)
    print(f"stopped at {done} examples after {calls} requests")