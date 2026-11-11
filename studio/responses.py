"""Explicit output contracts, including an answer-key-free practice contract."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .schemas import Citation, LimitsInput, QuizDraft


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Profile(Output):
    name: str | None


class AuthStatus(Output):
    authenticated: bool
    csrf: str
    mfa_required: bool = False
    setup_required: bool | None = None
    mfa_enabled: bool | None = None
    profile: Profile | None = None


class Operation(Output):
    ok: bool


class Health(Output):
    status: str
    app: str


class MFASetup(Output):
    secret: str
    uri: str


class RecoveryCodes(Output):
    recovery_codes: list[str]


class Page(Output):
    page: int = Field(ge=1, le=100)
    text: str
    scanned: bool


class Document(Output):
    id: str
    title: str
    filename: str
    created: float
    status: Literal["indexing", "ready", "needs_aws"]
    indexed: int = Field(ge=0)
    redactions: dict[str, int]
    page_count: int = Field(ge=1, le=100)
    chunk_count: int = Field(ge=0)
    scanned_pages: list[int]
    error: str | None = None
    cached: bool = False


class DocumentDetail(Document):
    pages: list[Page]


class Narration(Output):
    text: str
    page: int


class SourceCitation(Citation):
    document_id: str


class Answer(Output):
    answer: str
    supported: bool
    citations: list[SourceCitation]


class Quiz(QuizDraft):
    id: str
    document_id: str
    created: float


class QuizSummary(Output):
    id: str
    document_id: str
    title: str
    created: float
    count: int
    needs_review: bool


class PracticeQuestion(Output):
    id: str
    type: Literal["mcq", "short", "medium"]
    prompt: str
    options: list[str]
    marks: int
    pages: list[int]
    needs_review: bool


class Feedback(Output):
    score: float = Field(ge=0, le=20)
    feedback: str
    pages: list[int]
    correct_answer: str


class Attempt(Output):
    id: str
    quiz_id: str
    document_id: str
    title: str
    mode: Literal["practice", "self-test"]
    questions: list[PracticeQuestion]
    answers: dict[str, str]
    grades: dict[str, Feedback]
    submitted: bool
    created: float
    total_marks: int
    score: float


class Activity(Output):
    id: str
    event: str
    decision: Literal["allowed", "blocked", "failed"]
    reason: str
    document_id: str | None
    timestamp: float


class Security(Output):
    mfa_enabled: bool
    limits: LimitsInput
    usage: dict[str, float]
    tokens: dict[str, float]
    controls: dict[str, bool | str]
    events: list[Activity]
    data_location: str


class AWSStatus(Output):
    authenticated: bool
    message: str | None = None
    region: str | None = None
    models: list[str] | None = None
