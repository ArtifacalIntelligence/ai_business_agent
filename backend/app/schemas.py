from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    task: str
    owner: str | None = None
    deadline: str | None = None  # kept as text, e.g. "Friday"


class MeetingAnalysis(BaseModel):
    summary: str
    participants: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    follow_up_needed: bool = False
    follow_up_reason: str | None = None