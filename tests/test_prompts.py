from src.services.openai_llm.prompts import RAGPromptBuilder, ResponseParser


class TestRAGPromptBuilder:
    def test_prompt_includes_query(self):
        builder = RAGPromptBuilder()
        prompt = builder.create_rag_prompt("What is a transformer?", chunks=[])
        assert "What is a transformer?" in prompt

    def test_prompt_cites_chunk_arxiv_id(self):
        builder = RAGPromptBuilder()
        chunks = [{"chunk_text": "Transformers use self-attention.", "arxiv_id": "2607.01218v1"}]
        prompt = builder.create_rag_prompt("What is a transformer?", chunks)

        assert "arXiv:2607.01218v1" in prompt
        assert "Transformers use self-attention." in prompt

    def test_prompt_with_multiple_chunks_numbers_them_in_order(self):
        builder = RAGPromptBuilder()
        chunks = [
            {"chunk_text": "first", "arxiv_id": "a1"},
            {"chunk_text": "second", "arxiv_id": "a2"},
        ]
        prompt = builder.create_rag_prompt("q", chunks)

        assert prompt.index("[1. arXiv:a1]") < prompt.index("[2. arXiv:a2]")

    def test_prompt_falls_back_to_content_key(self):
        builder = RAGPromptBuilder()
        chunks = [{"content": "fallback text", "arxiv_id": "a1"}]
        prompt = builder.create_rag_prompt("q", chunks)
        assert "fallback text" in prompt

    def test_empty_chunks_still_produces_valid_prompt(self):
        builder = RAGPromptBuilder()
        prompt = builder.create_rag_prompt("q", [])
        assert "### Question:" in prompt
        assert "### Context from Papers:" in prompt

    def test_structured_prompt_includes_json_schema(self):
        builder = RAGPromptBuilder()
        structured = builder.create_structured_prompt("q", [])
        assert "prompt" in structured
        assert "format" in structured


class TestResponseParser:
    def test_parses_valid_json_response(self):
        response = '{"answer": "Transformers use attention.", "sources": ["a1"], "confidence": "high", "citations": ["a1"]}'
        result = ResponseParser.parse_structured_response(response)
        assert result["answer"] == "Transformers use attention."
        assert result["sources"] == ["a1"]

    def test_extracts_json_embedded_in_extra_text(self):
        response = 'Here is the answer:\n{"answer": "x", "sources": [], "confidence": "low", "citations": []}\nHope that helps!'
        result = ResponseParser.parse_structured_response(response)
        assert result["answer"] == "x"

    def test_falls_back_to_plain_text_on_unparseable_response(self):
        response = "This is not JSON at all."
        result = ResponseParser.parse_structured_response(response)
        assert result["answer"] == response
        assert result["confidence"] == "low"
        assert result["sources"] == []
