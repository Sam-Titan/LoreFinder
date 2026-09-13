"""Regression suite: ingest known novels and check query answers/citations.

Run subsets with markers, e.g.:
    pytest -m smoke          # fast narrow-query checks only
    pytest -m "not slow"     # everything except the Monte Cristo stress case
    pytest                   # the whole suite
"""
import pytest

from .conftest import ensure_ingested, run_query

NOVELS = {
    "alice": {
        "title": "Alice's Adventures in Wonderland",
        "author": "Lewis Carroll",
    },
    "frankenstein": {
        "title": "Frankenstein",
        "author": "Mary Shelley",
    },
    "jekyll_hyde": {
        "title": "The Strange Case of Dr. Jekyll and Mr. Hyde",
        "author": "Robert Louis Stevenson",
    },
    "monte_cristo": {
        "title": "The Count of Monte Cristo",
        "author": "Alexandre Dumas",
    },
}

# Known failure-fallback strings from bugs we've already hit and fixed —
# if any of these show up again, that's a regression, not a legitimate answer.
_KNOWN_FALLBACKS = [
    "couldn't be summarized directly",
    "do not contain any information",
]

# (novel_key, query, any-of these keywords must appear, min matches required)
_RAW_CASES = [
    (
        "alice", "What color are the White Rabbit's eyes?",
        ["pink"], 1, "smoke",
    ),
    (
        "alice", "Summarize the events and strange rules of the croquet game with the Queen.",
        ["flamingo", "hedgehog", "head"], 2, "full",
    ),
    (
        "frankenstein",
        "What is the name of the professor at Ingolstadt who encourages Victor "
        "to study modern chemistry?",
        ["waldman"], 1, "smoke",
    ),
    (
        "frankenstein",
        "What is the exact relationship between Robert Walton and Margaret Saville?",
        ["sister"], 1, "smoke",
    ),
    (
        "frankenstein",
        "Summarize the monster's experience living in the hovel and observing the cottagers.",
        ["cottage", "family", "felix", "agatha", "language"], 2, "full",
    ),
    (
        "jekyll_hyde",
        "Summarize how Mr. Utterson's theories about Mr. Hyde's relationship with Dr. Jekyll "
        "evolve from the beginning of the investigation to the final confession.",
        ["jekyll", "hyde"], 2, "full",
    ),
    (
        "monte_cristo",
        "What is the name of the merchant ship Edmond Dantes was first mate on when he was "
        "arrested, at the start of the novel?",
        ["pharaon"], 1, "slow",
    ),
]

CASES = [
    pytest.param(
        novel_key, query, required_any, min_matches,
        marks=getattr(pytest.mark, marker),
        id=f"{novel_key}-{query[:40]}",
    )
    for novel_key, query, required_any, min_matches, marker in _RAW_CASES
]


def _assert_answer_sane(result: dict, required_any: list[str], min_matches: int):
    answer = result["response"]
    assert answer.strip(), "answer was empty"

    lowered = answer.lower()
    for fallback in _KNOWN_FALLBACKS:
        assert fallback not in lowered, (
            f"answer hit a known failure-fallback string ({fallback!r}) — "
            f"this is the empty-answer / reasoning-exhaustion bug regressing. Answer: {answer!r}"
        )

    matches = sum(1 for kw in required_any if kw.lower() in lowered)
    assert matches >= min_matches, (
        f"expected at least {min_matches} of {required_any} in the answer, found {matches}. "
        f"Answer: {answer!r}"
    )

    # Citation sanity — guards the chapter_number/chapter_title mismatch bug.
    for ref in result["references"]:
        assert isinstance(ref["chapter_number"], int) and ref["chapter_number"] > 0
        assert ref.get("chapter_title"), f"citation missing chapter_title: {ref!r}"
        assert isinstance(ref["chunk_index"], int) and ref["chunk_index"] >= 0


@pytest.mark.parametrize("novel_key,query,required_any,min_matches", CASES)
def test_novel_query(novel_key, query, required_any, min_matches):
    doc_id = ensure_ingested(NOVELS[novel_key])
    result = run_query(doc_id, query)
    _assert_answer_sane(result, required_any, min_matches)
