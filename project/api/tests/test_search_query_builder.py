from __future__ import annotations

from app.services.search.publications import build_search_query, MetricFilter, SearchFilters


def test_search_query_builder_includes_soft_delete_filter():
    query = build_search_query("hello", filters=None)
    assert {"exists": {"field": "deleted_at"}} in query["bool"]["must_not"]


def test_search_query_builder_metrics_filter():
    filters = SearchFilters(metrics=[MetricFilter(field="views", gte=10)])
    query = build_search_query(None, filters=filters)
    range_filter = {"range": {"metrics.views": {"gte": 10}}}
    assert range_filter in query["bool"]["filter"]
