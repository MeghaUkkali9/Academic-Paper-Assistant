from tests.conftest import make_paper


class TestChunkText:
    def test_empty_text_returns_no_chunks(self, chunker):
        assert chunker.chunk_text("", arxiv_id="2607.00001v1", paper_id="p1") == []

    def test_whitespace_only_text_returns_no_chunks(self, chunker):
        assert chunker.chunk_text("   \n\t  ", arxiv_id="2607.00001v1", paper_id="p1") == []

    def test_text_below_minimum_returns_single_chunk(self, chunker):
        text = " ".join(["word"] * 50)  # below min_chunk_size=100
        chunks = chunker.chunk_text(text, arxiv_id="2607.00001v1", paper_id="p1")
        assert len(chunks) == 1
        assert chunks[0].metadata.word_count == 50

    def test_long_text_produces_overlapping_chunks(self, chunker):
        # 1400 words, chunk_size=600, overlap=100 -> step=500 -> starts at 0, 500, 1000
        text = " ".join(f"word{i}" for i in range(1400))
        chunks = chunker.chunk_text(text, arxiv_id="2607.00001v1", paper_id="p1")

        assert len(chunks) == 3
        assert chunks[0].metadata.start_char == 0
        assert chunks[0].metadata.word_count == 600
        # second chunk should start 500 words in, overlapping 100 words with the first
        assert chunks[1].text.split()[0] == "word500"
        assert chunks[1].metadata.overlap_with_previous == 100

    def test_chunk_indices_are_sequential(self, chunker):
        text = " ".join(f"word{i}" for i in range(1400))
        chunks = chunker.chunk_text(text, arxiv_id="2607.00001v1", paper_id="p1")
        assert [c.metadata.chunk_index for c in chunks] == [0, 1, 2]

    def test_last_chunk_has_no_overlap_with_next(self, chunker):
        text = " ".join(f"word{i}" for i in range(1400))
        chunks = chunker.chunk_text(text, arxiv_id="2607.00001v1", paper_id="p1")
        assert chunks[-1].metadata.overlap_with_next == 0


class TestChunkPaper:
    def test_no_sections_falls_back_to_word_chunking(self, chunker):
        paper = make_paper(raw_text=" ".join(["word"] * 300), sections=None)
        chunks = chunker.chunk_paper(paper)
        assert len(chunks) == 1
        assert chunks[0].metadata.section_title is None

    def test_mid_size_section_becomes_single_chunk(self, chunker):
        section_text = " ".join(["result"] * 300)  # within 100-800 word range
        paper = make_paper(sections=[{"title": "Results", "content": section_text}])
        chunks = chunker.chunk_paper(paper)

        assert len(chunks) == 1
        assert chunks[0].metadata.section_title == "Results"
        assert "Section: Results" in chunks[0].text
        assert paper.title in chunks[0].text

    def test_metadata_sections_are_filtered_out(self, chunker):
        section_text = " ".join(["result"] * 300)
        paper = make_paper(
            sections=[
                {"title": "Authors", "content": "Jane Doe, jane@example.edu"},
                {"title": "Results", "content": section_text},
            ]
        )
        chunks = chunker.chunk_paper(paper)

        titles = [c.metadata.section_title for c in chunks]
        assert "Authors" not in titles
        assert "Results" in titles

    def test_section_duplicating_abstract_is_filtered_out(self, chunker):
        abstract = "This paper studies how to test software effectively and thoroughly."
        section_text = " ".join(["result"] * 300)
        paper = make_paper(
            abstract=abstract,
            sections=[
                {"title": "Abstract", "content": abstract},
                {"title": "Results", "content": section_text},
            ],
        )
        chunks = chunker.chunk_paper(paper)

        titles = [c.metadata.section_title for c in chunks]
        assert "Abstract" not in titles
        assert "Results" in titles

    def test_small_sections_are_combined(self, chunker):
        paper = make_paper(
            sections=[
                {"title": "Intro", "content": " ".join(["intro"] * 30)},
                {"title": "Motivation", "content": " ".join(["motive"] * 30)},
            ]
        )
        chunks = chunker.chunk_paper(paper)

        assert len(chunks) == 1
        assert "Intro" in chunks[0].metadata.section_title
        assert "Motivation" in chunks[0].metadata.section_title

    def test_large_section_is_split_into_parts(self, chunker):
        section_text = " ".join(f"word{i}" for i in range(1000))  # > 800 words
        paper = make_paper(sections=[{"title": "Methodology", "content": section_text}])
        chunks = chunker.chunk_paper(paper)

        assert len(chunks) > 1
        assert all("Methodology (Part" in c.metadata.section_title for c in chunks)

    def test_parse_sections_accepts_json_string(self, chunker):
        # PaperForIndexing.sections is typed as a list, so a JSON string can
        # never reach chunk_paper in practice — but _parse_sections defends
        # against it anyway, worth pinning directly.
        parsed = chunker._parse_sections('{"Results": "some content"}')
        assert parsed == {"Results": "some content"}

    def test_parse_sections_returns_empty_dict_on_invalid_json_string(self, chunker):
        assert chunker._parse_sections("not valid json") == {}

    def test_empty_sections_falls_back_to_word_chunking(self, chunker):
        paper = make_paper(raw_text=" ".join(["word"] * 300), sections=[])
        chunks = chunker.chunk_paper(paper)
        assert len(chunks) == 1
        assert chunks[0].metadata.section_title is None
