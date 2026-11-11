from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PasswordInput(Input):
    password: SecretStr = Field(min_length=12, max_length=128)


class LoginInput(Input):
    password: SecretStr = Field(min_length=1, max_length=128)


class CodeInput(Input):
    code: str = Field(min_length=6, max_length=40, pattern=r"^[A-Za-z0-9 -]+$")


class MFAOff(PasswordInput):
    code: str = Field(min_length=6, max_length=40, pattern=r"^[A-Za-z0-9 -]+$")


class ProfileInput(Input):
    name: str | None = Field(default=None, max_length=200)


class LimitsInput(Input):
    text: int = Field(ge=1, le=1000)
    quiz: int = Field(ge=1, le=100)
    voice_seconds: int = Field(ge=30, le=7200)


class AskInput(Input):
    document_id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=3000)
    page: int | None = Field(default=None, ge=1, le=100)


class Citation(Input):
    page: int = Field(ge=1, le=100)
    excerpt: str = Field(min_length=1, max_length=1200)


class Answer(Input):
    answer: str = Field(min_length=1, max_length=6000)
    citations: list[Citation] = Field(default_factory=list, max_length=8)
    supported: bool


class Question(Input):
    id: str = Field(min_length=1, max_length=80)
    type: Literal["mcq", "short", "medium"]
    prompt: str = Field(min_length=1, max_length=3000)
    options: list[str] = Field(default_factory=list, max_length=4)
    correct_index: int | None = Field(default=None, ge=0, le=3)
    model_answer: str = Field(default="", max_length=5000)
    rubric: str = Field(default="", max_length=4000)
    explanation: str = Field(min_length=1, max_length=4000)
    marks: int = Field(default=1, ge=1, le=20)
    pages: list[int] = Field(min_length=1, max_length=10)
    needs_review: bool = False

    @model_validator(mode="after")
    def valid(self):
        if self.type == "mcq":
            if len(self.options) != 4 or len(set(self.options)) != 4 or any(not option.strip() for option in self.options) or self.correct_index is None:
                raise ValueError("Multiple-choice questions need four unique options and a correct answer.")
        elif not self.model_answer.strip() or not self.rubric.strip():
            raise ValueError("Written questions need a model answer and marking rubric.")
        if any(page < 1 or page > 100 for page in self.pages):
            raise ValueError("Invalid source page.")
        return self


class QuizDraft(Input):
    title: str = Field(min_length=1, max_length=160)
    questions: list[Question] = Field(min_length=1, max_length=20)


class GenerateInput(Input):
    document_id: str = Field(min_length=1, max_length=80)
    count: int = Field(default=6, ge=1, le=20)
    types: list[Literal["mcq", "short", "medium"]] = Field(default_factory=lambda: ["mcq", "short", "medium"], min_length=1, max_length=3)
    difficulty: Literal["foundation", "intermediate", "advanced"] = "foundation"
    pages: list[int] = Field(default_factory=list, max_length=100)


class StartAttempt(Input):
    mode: Literal["practice", "self-test"]


class SubmitAnswer(Input):
    question_id: str = Field(min_length=1, max_length=80)
    answer: str = Field(max_length=6000)


class Grade(Input):
    score: float = Field(ge=0, le=20)
    feedback: str = Field(min_length=1, max_length=3000)


class NarrateInput(Input):
    page: int = Field(ge=1, le=100)
    selection: str | None = Field(default=None, max_length=12000)
