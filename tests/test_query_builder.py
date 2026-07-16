from src.services.opensearch.query import QueryBuilder


class TestBuildQuery:
    def test_empty_query_uses_match_all(self):
        builder = QueryBuilder(query="")
        body = builder.build()
        assert body["query"]["bool"]["must"] == [{"match_all": {}}]

    def test_text_query_uses_multi_match(self):
        builder = QueryBuilder(query="transformers")
        body = builder.build()
        must = body["query"]["bool"]["must"][0]
        assert must["multi_match"]["query"] == "transformers"

    def test_chunk_search_fields_differ_from_paper_search(self):
        chunk_fields = QueryBuilder(query="x", search_chunks=True).fields
        paper_fields = QueryBuilder(query="x", search_chunks=False).fields
        assert "chunk_text^3" in chunk_fields
        assert "chunk_text^3" not in paper_fields
        assert "authors^1" in paper_fields

    def test_custom_fields_override_defaults(self):
        builder = QueryBuilder(query="x", fields=["title^5"])
        assert builder.fields == ["title^5"]

    def test_categories_add_filter_clause(self):
        builder = QueryBuilder(query="x", categories=["cs.AI", "cs.LG"])
        body = builder.build()
        assert {"terms": {"categories": ["cs.AI", "cs.LG"]}} in body["query"]["bool"]["filter"]

    def test_no_categories_means_no_filter_clause(self):
        builder = QueryBuilder(query="x")
        body = builder.build()
        assert "filter" not in body["query"]["bool"]


class TestSourceFields:
    def test_chunk_search_excludes_embedding(self):
        body = QueryBuilder(query="x", search_chunks=True).build()
        assert body["_source"] == {"excludes": ["embedding"]}

    def test_paper_search_returns_explicit_field_list(self):
        body = QueryBuilder(query="x", search_chunks=False).build()
        assert "embedding" not in body["_source"]
        assert "arxiv_id" in body["_source"]


class TestSort:
    def test_latest_papers_sorts_by_date_desc(self):
        body = QueryBuilder(query="x", latest_papers=True).build()
        assert body["sort"][0] == {"published_date": {"order": "desc"}}

    def test_text_query_without_latest_has_no_forced_sort(self):
        body = QueryBuilder(query="transformers", latest_papers=False).build()
        assert "sort" not in body

    def test_empty_query_defaults_to_date_sort(self):
        body = QueryBuilder(query="", latest_papers=False).build()
        assert body["sort"][0] == {"published_date": {"order": "desc"}}


class TestPaginationAndSizing:
    def test_size_and_from_are_passed_through(self):
        body = QueryBuilder(query="x", size=5, from_=10).build()
        assert body["size"] == 5
        assert body["from"] == 10
