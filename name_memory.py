"""Store Jozi Buddy's preferred-name memory locally."""

import json
from pathlib import Path
import re
import unicodedata


DEFAULT_MEMORY_PATH = Path(__file__).resolve().parent / ".memory" / "user.json"

_NAME_SEPARATORS = frozenset(" '-’‘.")
_INSTRUCTION_PATTERN = re.compile(
    r"\b(?:ignore|disregard|override|reveal|instructions?|password|"
    r"passcode|credentials?|secret|token|api\s+key|system\s+prompt)\b",
    re.IGNORECASE,
)
_INVALID_NAME_MESSAGE = (
    "I can save a preferred name only. Use letters, spaces, apostrophes, "
    "hyphens, or initials, and leave out numbers, contact details, secrets, "
    "and instructions."
)


def validate_name(name: str) -> str:
    """Normalize a name and reject obvious non-name or sensitive payloads.

    This format check limits what can enter the name file. The conversation's
    privacy instructions handle the meaning of requests; this is not a
    general-purpose detector for every kind of personal information.
    """
    if not isinstance(name, str):
        raise ValueError(_INVALID_NAME_MESSAGE)
    name = " ".join(name.split())
    if not name or len(name) > 200 or _INSTRUCTION_PATTERN.search(name):
        raise ValueError(_INVALID_NAME_MESSAGE)
    if not any(character.isalpha() for character in name):
        raise ValueError(_INVALID_NAME_MESSAGE)
    if any(
        not (
            character.isalpha()
            or unicodedata.category(character).startswith("M")
            or character in _NAME_SEPARATORS
        )
        for character in name
    ):
        raise ValueError(_INVALID_NAME_MESSAGE)
    return name


class NameMemory:
    """Read, update, and remove a single preferred name."""

    def __init__(self, path: Path = DEFAULT_MEMORY_PATH) -> None:
        self.path = path

    def load_name(self) -> str | None:
        """Return a saved name, or None for missing or malformed memory."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
            return None

        name = data.get("name") if isinstance(data, dict) else None
        try:
            return validate_name(name)
        except ValueError:
            return None

    def save_name(self, name: str) -> str:
        """Save a nonempty preferred name and return its normalized form."""
        name = validate_name(name)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        try:
            temporary_path.write_text(
                json.dumps({"name": name}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return name

    def forget_name(self) -> None:
        """Remove the saved name; forgetting an absent name is harmless."""
        self.path.unlink(missing_ok=True)
