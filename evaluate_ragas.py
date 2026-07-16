"""Evaluate the RAG pipeline with RAGAS (faithfulness, answer relevancy, context precision).

Usage:
    python3 evaluate_ragas.py                  # hybrid search (default)
    python3 evaluate_ragas.py --mode bm25       # BM25-only, for comparison
    python3 evaluate_ragas.py --mode agentic    # agentic RAG (routing/grading/retry/groundedness)

On first run, generates one eval question per indexed paper and saves them to
evaluation_questions.json for reuse/review (shared across modes, so the
comparison uses identical questions). Delete that file to regenerate.
Per-question results are written to evaluation_results_<mode>.csv.
"""
import argparse
import asyncio
import json
import logging
import warnings
from pathlib import Path

from sqlalchemy import text

warnings.filterwarnings("ignore", category=DeprecationWarning, module="ragas")

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import AsyncOpenAI
from ragas import EvaluationDataset, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, LLMContextPrecisionWithoutReference, ResponseRelevancy

from src.config import get_settings
from src.database.factory import create_database
from src.services.agent.factory import create_rag_agent
from src.services.embedding.factory import get_embedding_client
from src.services.openai_llm.factory import make_openai_llm_client
from src.services.opensearch.factory import get_opensearch_client

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

QUESTIONS_PATH = Path(__file__).parent / "evaluation_questions.json"
TOP_K = 3


def get_indexed_papers(database) -> list[dict]:
    with database.get_session() as session:
        rows = session.execute(
            text("SELECT arxiv_id, title, summary FROM research_paper WHERE is_indexed = true")
        ).fetchall()
    return [{"arxiv_id": r[0], "title": r[1], "abstract": r[2]} for r in rows]


async def generate_questions(openai_client: AsyncOpenAI, papers: list[dict]) -> list[dict]:
    """One factual question per paper, derived from its abstract."""
    questions = []

    for paper in papers:
        prompt = (
            "Write ONE specific factual question that a researcher could ask, "
            "which is directly answered by this paper's abstract. "
            "Return only the question, no preamble.\n\n"
            f"Title: {paper['title']}\nAbstract: {paper['abstract']}"
        )
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        question = response.choices[0].message.content.strip()
        questions.append({"question": question, "expected_arxiv_id": paper["arxiv_id"]})
        logger.info(f"Generated question for {paper['arxiv_id']}: {question}")

    return questions


async def run_rag(
    question: str, opensearch_client, embedding_client, llm_client, use_hybrid: bool
) -> tuple[str, list[str]]:
    query_embedding = await embedding_client.embed_query(question) if use_hybrid else None
    results = opensearch_client.search(
        query=question,
        query_embedding=query_embedding,
        size=TOP_K,
        use_hybrid=use_hybrid,
    )
    chunks = [
        {"arxiv_id": hit.get("arxiv_id", ""), "chunk_text": hit.get("chunk_text", "")}
        for hit in results.get("hits", [])
    ]
    if not chunks:
        return "No relevant information found.", []

    result = await llm_client.generate_rag_answer(query=question, chunks=chunks)
    contexts = [c["chunk_text"] for c in chunks]
    return result["answer"], contexts


async def run_agentic_rag(question: str, graph, use_hybrid: bool) -> tuple[str, list[str], dict]:
    """Run a question through the compiled agentic graph. Returns (answer,
    contexts, stats) where stats carries the graph's own decision metadata
    (retrieval attempts, grounded, guardrail_triggered) for comparison
    against RAGAS's independent judgment of the same answer."""
    initial_state = {
        "query": question,
        "original_query": question,
        "top_k": TOP_K,
        "categories": None,
        "model": "gpt-4o-mini",
        "use_hybrid": use_hybrid,
        "retrieved_chunks": [],
        "graded_chunks": [],
        "sources": [],
        "search_mode": "bm25",
        "retrieval_retry_count": 0,
        "generation_retry_count": 0,
        "in_scope": True,
        "is_grounded": False,
        "answer": "",
        "guardrail_reason": None,
    }

    final_state = await graph.ainvoke(initial_state, config={"recursion_limit": 25})
    contexts = [c["chunk_text"] for c in final_state["graded_chunks"]]
    stats = {
        "retrieval_attempts": final_state["retrieval_retry_count"] + 1,
        "chunks_graded_relevant": len(final_state["graded_chunks"]),
        "graph_grounded": final_state["is_grounded"],
        "guardrail_triggered": final_state["guardrail_reason"],
    }
    return final_state["answer"], contexts, stats


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["hybrid", "bm25", "agentic"], default="hybrid")
    args = parser.parse_args()
    use_hybrid = args.mode != "bm25"  # both hybrid and agentic modes use hybrid retrieval
    results_path = Path(__file__).parent / f"evaluation_results_{args.mode}.csv"

    settings = get_settings()
    database = create_database()
    opensearch_client = get_opensearch_client()
    embedding_client = get_embedding_client()
    llm_client = make_openai_llm_client()
    rag_agent = create_rag_agent(opensearch_client, embedding_client, llm_client, settings) if args.mode == "agentic" else None

    if QUESTIONS_PATH.exists():
        questions = json.loads(QUESTIONS_PATH.read_text())
        print(f"Loaded {len(questions)} existing questions from {QUESTIONS_PATH}")
    else:
        papers = get_indexed_papers(database)
        if not papers:
            print("No indexed papers found. Run indexing first.")
            return

        print(f"Generating {len(papers)} eval questions from indexed papers...")
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        questions = await generate_questions(openai_client, papers)
        QUESTIONS_PATH.write_text(json.dumps(questions, indent=2))
        print(f"Saved questions to {QUESTIONS_PATH}")

    samples = []
    agentic_stats = []
    for q in questions:
        question = q["question"]
        print(f"Running RAG for: {question}")

        if args.mode == "agentic":
            answer, contexts, stats = await run_agentic_rag(question, rag_agent, use_hybrid)
            agentic_stats.append(stats)
        else:
            answer, contexts = await run_rag(question, opensearch_client, embedding_client, llm_client, use_hybrid)

        samples.append(
            {
                "user_input": question,
                "response": answer,
                "retrieved_contexts": contexts or [""],
            }
        )

    dataset = EvaluationDataset.from_list(samples)

    evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key, temperature=0))
    evaluator_embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(api_key=settings.openai_api_key))

    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), ResponseRelevancy(), LLMContextPrecisionWithoutReference()],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
    )

    print(f"\n=== RAGAS Scores (averaged, mode={args.mode}) ===")
    print(result)

    df = result.to_pandas()

    if agentic_stats:
        for key in ("retrieval_attempts", "chunks_graded_relevant", "graph_grounded", "guardrail_triggered"):
            df[key] = [s[key] for s in agentic_stats]

        avg_attempts = sum(s["retrieval_attempts"] for s in agentic_stats) / len(agentic_stats)
        retried = sum(1 for s in agentic_stats if s["retrieval_attempts"] > 1)
        rejected = sum(1 for s in agentic_stats if s["guardrail_triggered"])
        graph_grounded_count = sum(1 for s in agentic_stats if s["graph_grounded"])
        ragas_grounded_count = sum(1 for v in df["faithfulness"] if v >= 0.8)

        print("\n=== Agentic graph stats ===")
        print(f"Avg retrieval attempts: {avg_attempts:.2f}")
        print(f"Questions that needed a retry: {retried}/{len(agentic_stats)}")
        print(f"Questions rejected by guardrails: {rejected}/{len(agentic_stats)}")
        print(f"Graph's own groundedness check said grounded: {graph_grounded_count}/{len(agentic_stats)}")
        print(f"RAGAS faithfulness >= 0.8 (independent judge): {ragas_grounded_count}/{len(agentic_stats)}")

    df.to_csv(results_path, index=False)
    print(f"\nPer-question results saved to {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
