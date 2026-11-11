"""Bounded spelling hints and conservative handling of spoken technical acronyms."""
import re
from collections import Counter

from .privacy import redact


def document_terms(document):
    # Only short acronym-shaped tokens become hints, never document sentences.
    text = "\n".join(redact(page["text"])[0] for page in document["pages"] if not page["scanned"])
    counts = Counter(re.findall(r"\b[A-Z][A-Z0-9]{1,7}(?:-[A-Z0-9]{2,8})?\b", text))
    for label in ("REDACTED", "EMAIL", "PHONE", "ID", "ADDRESS", "SECRET", "TOKEN", "PASSWORD"):
        counts.pop(label, None)
    return sorted(counts, key=lambda term: ("-" not in term, -counts[term], term))[:32]


_SPELLED = re.compile(r"\b[A-Za-z](?:[ .]+[A-Za-z]){2,11}(?:\s+(?:dash|hyphen)\s+(?:[A-Za-z](?:[ .]+[A-Za-z]){1,7}|[A-Za-z]{2,8}))?\b", re.IGNORECASE)
_COMPOUND = re.compile(r"\b[A-Z]{2,8}[-–][A-Z0-9]{2,8}\b")


def checked_spelling(question, terms):
    """Join explicitly spoken letters only; never fuzzy-correct a different acronym.

    Returns (question, clarification). A clarification bypasses the text model.
    This cannot detect every ASR error or prove that a transcript is accurate.
    """
    known = {term.casefold(): term for term in terms}
    unclear = False

    def join(match):
        nonlocal unclear
        heard = re.sub(r"\s+(?:dash|hyphen)\s+", "-", match.group(), flags=re.IGNORECASE)
        heard = re.sub(r"[ .]", "", heard).upper()
        if heard.casefold() in known:
            return known[heard.casefold()]
        unclear = True
        return match.group()

    corrected = _SPELLED.sub(join, question)
    def compound(match):
        nonlocal unclear
        heard = f"{match[1]}-{match[2]}".upper()
        if heard.casefold() in known:
            return known[heard.casefold()]
        unclear = True
        return match.group()
    corrected = re.sub(r"\b([A-Za-z]{2,8})\s+(?:dash|hyphen)\s+([A-Za-z]{2,8})\b", compound, corrected, flags=re.IGNORECASE)
    if any(match.group().replace("–", "-").casefold() not in known for match in _COMPOUND.finditer(corrected)):
        unclear = True
    if unclear:
        return question, "I may have misheard those letters. Please use Correct in text to enter the exact term, so I don't guess your question."
    return corrected, None
