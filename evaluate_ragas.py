"""Evaluate the RAG pipeline with RAGAS (faithfulness, answer relevancy, context precision).

Usage:
    python3 evaluate_ragas.py

On first run, generates one eval question per indexed paper and saves them to
evaluation_questions.json for reuse/review. Delete that file to regenerate.
Per-question results are written to evaluation_results.csv.
"""
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
from src.services.embedding.factory import get_embedding_client
from src.services.openai_llm.factory import make_openai_llm_client
from src.services.opensearch.factory import get_opensearch_client

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

QUESTIONS_PATH = Path(__file__).parent / "evaluation_questions.json"
RESULTS_PATH = Path(__file__).parent / "evaluation_results.csv"
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


async def run_rag(question: str, opensearch_client, embedding_client, llm_client) -> tuple[str, list[str]]:
    query_embedding = await embedding_client.embed_query(question)
    results = opensearch_client.search(
        query=question,
        query_embedding=query_embedding,
        size=TOP_K,
        use_hybrid=True,
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


async def main():
    settings = get_settings()
    database = create_database()
    opensearch_client = get_opensearch_client()
    embedding_client = get_embedding_client()
    llm_client = make_openai_llm_client()

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
    for q in questions:
        question = q["question"]
        print(f"Running RAG for: {question}")
        answer, contexts = await run_rag(question, opensearch_client, embedding_client, llm_client)
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

    print("\n=== RAGAS Scores (averaged) ===")
    print(result)

    df = result.to_pandas()
    df.to_csv(RESULTS_PATH, index=False)
    print(f"\nPer-question results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
