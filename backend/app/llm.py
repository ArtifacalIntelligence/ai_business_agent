import os
import time
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from app.schemas import MeetingAnalysis

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# LangChain's Gemini integration reads GOOGLE_API_KEY, so reuse your existing key
if "GEMINI_API_KEY" in os.environ:
    os.environ.setdefault("GOOGLE_API_KEY", os.environ["GEMINI_API_KEY"])

SYSTEM_PROMPT = """You analyze business meeting transcripts and documents.
Rules:
- Use ONLY information stated in the text. Never invent facts.
- If an action item has no stated owner or deadline, use null for it.
- decisions = things the group agreed or decided.
- concerns = risks, blockers or worries that were raised.
- follow_up_needed = true only if the text says another meeting or check-in is needed.
- Keep the summary to 2-4 sentences."""

_chain = None


def get_chain():
    """prompt -> Gemini -> validated MeetingAnalysis object"""
    global _chain
    if _chain is None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "Analyze this meeting transcript or business document:\n\n{text}"),
        ])
        model = ChatGoogleGenerativeAI(model=MODEL, temperature=0.2)
        _chain = prompt | model.with_structured_output(MeetingAnalysis)
    return _chain


def analyze_text(text: str, retries: int = 3) -> MeetingAnalysis:
    last_err = None
    for attempt in range(retries):
        try:
            result = get_chain().invoke({"text": text[:30000]})
            if isinstance(result, dict):
                result = MeetingAnalysis.model_validate(result)
            return result
        except Exception as e:  # network, quota, or invalid output
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"AI analysis failed after {retries} tries: {last_err}")