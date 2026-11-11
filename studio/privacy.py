"""Local redaction of common identifiers. Detection is deliberately documented as heuristic."""
import re
from collections import Counter
import phonenumbers

PATTERNS = (
    ("CREDENTIAL", re.compile(r'''(?i)\b(?:aws_secret_access_key|password|passwd|api[_ -]?key|secret[_ -]?key|access[_ -]?token)\s*[:=]\s*(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;]+)''')),
    ("CREDENTIAL", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("CREDENTIAL", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")),
    ("FINANCIAL", re.compile(r"(?i)\b(?:bank\s+account|account\s+number|iban)\s*[:=]\s*[A-Z0-9][A-Z0-9 -]{5,33}\b")),
    ("ID", re.compile(r"(?i)\b(?:passport|identity\s+number|id\s+number)\s*[:=]\s*[A-Z0-9-]{6,20}\b")),
    ("AWS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("ID", re.compile(r"(?<!\d)\d{13}(?!\d)")),
    ("CARD", re.compile(r"(?<!\d)(?:\d[ -]?){15,19}(?!\d)")),
    ("ADDRESS", re.compile(r"(?i)\b\d{1,5}\s+[\w .'-]{2,55}\s(?:street|road|avenue|lane|drive|crescent|close|st|rd|ave)\b")),
)


def redact(text: str) -> tuple[str, dict[str, int]]:
    spans = []
    for label, pattern in PATTERNS:
        spans.extend((match.start(), match.end(), label) for match in pattern.finditer(text))
    for match in phonenumbers.PhoneNumberMatcher(text, "ZA"):
        spans.append((match.start, match.end, "PHONE"))
    # Explicitly labelled numbers are masked even if they are not assigned numbers.
    for match in re.finditer(r"(?i)\b(?:phone|mobile|tel|cell)\s*[:=]?\s*(\+?[\d ()-]{7,22})", text):
        spans.append((match.start(1), match.end(1), "PHONE"))
    chosen, end = [], -1
    for start, stop, label in sorted(spans, key=lambda item: (item[0], -(item[1] - item[0]))):
        if start >= end:
            chosen.append((start, stop, label))
            end = stop
    counts = Counter(label for _, _, label in chosen)
    for start, stop, label in reversed(chosen):
        text = text[:start] + f"[REDACTED_{label}]" + text[stop:]
    return text, dict(counts)


def redact_data(value):
    """Redact string values before JSON encoding, preserving syntax and identifiers."""
    if isinstance(value, str):
        return redact(value)[0]
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, dict):
        return {key: item if key in {"id", "document_id", "question_id", "hash", "type"} else redact_data(item) for key, item in value.items()}
    return value
