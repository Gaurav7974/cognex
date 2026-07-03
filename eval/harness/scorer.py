def score(retrieved: list[str], answer_keywords: list[str]) -> dict:
    retrieved_text = ' '.join(retrieved).lower()
    for keyword in answer_keywords:
        if keyword.lower() in retrieved_text:
            for mem in retrieved:
                if keyword.lower() in mem.lower():
                    return {'hit': True, 'matched_keyword': keyword, 'matched_memory': mem}
    return {'hit': False, 'matched_keyword': None, 'matched_memory': None}