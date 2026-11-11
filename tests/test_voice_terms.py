import re

import pytest

from studio.voice_terms import checked_spelling, document_terms


@pytest.mark.parametrize("question,expected", [
    ("What does A E S dash G C M do?", "What does AES-GCM do?"),
    ("What does a e s dash GCM do?", "What does AES-GCM do?"),
    ("What does AES dash GCM do?", "What does AES-GCM do?"),
    ("Explain C S R F protection.", "Explain CSRF protection."),
    ("How does encryption work?", "How does encryption work?"),
])
def test_explicit_letters_keep_their_spelling(question, expected):
    assert checked_spelling(question, ["AES-GCM", "CSRF"]) == (expected, None)


@pytest.mark.parametrize("question", ["What does A U B S dash G C M do?", "What does UBS-GCM do?", "What does aubs dash gcm do?"])
def test_unknown_acronyms_request_correction_instead_of_substitution(question):
    result, clarification = checked_spelling(question, ["AES-GCM", "CSRF"])
    assert result == question
    assert "Correct in text" in clarification
    assert "AES-GCM" not in clarification


def test_document_spelling_hints_are_bounded_redacted_tokens():
    pages = [{"text": "AES-GCM and CSRF. Password: PRIVATEKEY\n" + " ".join(f"TERM{i}" for i in range(100)), "scanned": False},
             {"text": "SCANNEDSECRET", "scanned": True}]
    terms = document_terms({"pages": pages})
    assert "AES-GCM" in terms and "CSRF" in terms
    assert "PRIVATEKEY" not in terms and "SCANNEDSECRET" not in terms
    assert len(terms) <= 32
    assert all(re.fullmatch(r"[A-Z][A-Z0-9]{1,7}(?:-[A-Z0-9]{2,8})?", term) for term in terms)
