"""LongMemEval scorer — keyword matching for retrieval evaluation."""


def score(
    retrieved: list[str],
    answer_keywords: list[str]
) -> dict:
    """Check if any answer_keyword appears in retrieved memories.
    
    Returns dict with:
    - hit: bool (True if any keyword matched)
    - matched_keyword: str | None (which keyword matched, if any)
    - matched_memory: str | None (which memory contained the match)
    """
    retrieved_text = " ".join(retrieved).lower()
    for keyword in answer_keywords:
        if keyword.lower() in retrieved_text:
            # Find which memory contained it
            for mem in retrieved:
                if keyword.lower() in mem.lower():
                    return {
                        "hit": True,
                        "matched_keyword": keyword,
                        "matched_memory": mem
                    }
    return {"hit": False, "matched_keyword": None, "matched_memory": None}
