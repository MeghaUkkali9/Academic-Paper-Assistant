from typing import Any, Dict, List


def build_pdf_sources(chunks: List[Dict[str, Any]]) -> List[str]:
    """Build deduplicated arXiv PDF URLs from a list of retrieved chunks."""
    sources_set = set()

    for chunk in chunks:
        arxiv_id = chunk.get("arxiv_id", "")
        if arxiv_id:
            arxiv_id_clean = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
            sources_set.add(f"https://arxiv.org/pdf/{arxiv_id_clean}.pdf")

    return list(sources_set)
