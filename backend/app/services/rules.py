import re
from difflib import SequenceMatcher

_NUM = re.compile(r"\d")
_LINK = re.compile(r"(https?://|www\.|№\s*\d|наказ|протокол|лист|акт\b|додаток)", re.IGNORECASE)
SIMILARITY_THRESHOLD = 0.75


def similarity(a: str, b: str) -> float:
    norm = lambda x: " ".join(re.findall(r"\w+", x.lower()))  # noqa: E731
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def vague_result_facts(title: str, description: str | None) -> dict | None:
    if not description:
        return None
    has_number = bool(_NUM.search(description))
    has_reference = bool(_LINK.search(description))
    sim = round(similarity(title, description), 2)
    repeats_title = sim >= SIMILARITY_THRESHOLD
    if repeats_title or not (has_number or has_reference):
        return {
            "similarityToTitle": sim,
            "threshold": SIMILARITY_THRESHOLD,
            "hasNumber": has_number,
            "hasReference": has_reference,
        }
    return None


def submit_hints(title: str, description: str | None, required_evidence: str, evidence_count: int) -> list[str]:
    hints = []
    facts = vague_result_facts(title, description)
    if facts:
        if facts["similarityToTitle"] >= SIMILARITY_THRESHOLD:
            hints.append("Опис результату майже повторює назву заходу — опишіть, що саме змінилось.")
        if not (facts["hasNumber"] or facts["hasReference"]):
            hints.append("Додайте вимірюваний показник (число) або посилання на документ (№ наказу, протоколу).")
    if required_evidence and evidence_count == 0:
        hints.append(f"Потрібні підтвердні матеріали: {required_evidence}")
    return hints
