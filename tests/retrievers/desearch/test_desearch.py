"""Isolated Desearch contract tests requiring only requests and pytest."""

import ast
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from live_check import load_retriever

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def search(monkeypatch):
    monkeypatch.setenv("DESEARCH_API_KEY", "unit-test-token")
    return load_retriever()("a query & symbols", query_domains=["example.org"])


def mock_http(monkeypatch, payload):
    response = Mock()
    response.json.return_value = payload
    get = Mock(return_value=response)
    monkeypatch.setattr(requests, "get", get)
    return get


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key(monkeypatch, key):
    if key is None:
        monkeypatch.delenv("DESEARCH_API_KEY", raising=False)
    else:
        monkeypatch.setenv("DESEARCH_API_KEY", key)
    with pytest.raises(ValueError, match="DESEARCH_API_KEY"):
        load_retriever()("query")


def test_request_and_normalization(search, monkeypatch, capsys):
    get = mock_http(monkeypatch, {"data": [
        {"title": "Title", "link": "https://example.org", "snippet": "Snippet"},
        {"link": "https://example.org/2"},
    ]})
    assert search.search(2) == [
        {"title": "Title", "href": "https://example.org", "body": "Snippet"},
        {"title": "", "href": "https://example.org/2", "body": ""},
    ]
    get.assert_called_once_with(
        "https://api.desearch.ai/web",
        params={"query": "a query & symbols", "num": 2},
        headers={"Authorization": "Bearer unit-test-token"}, timeout=20,
    )
    get.return_value.raise_for_status.assert_called_once()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("payload", [None, [], {}, {"data": None}, {"data": {}}, {"data": [None, 1, {}, {"link": ""}, {"link": 3}]}])
def test_malformed_payload(search, monkeypatch, payload):
    mock_http(monkeypatch, payload)
    assert search.search() == []


def test_result_limit_and_null_fields(search, monkeypatch):
    mock_http(monkeypatch, {"data": [{"link": "https://example.org", "title": None, "snippet": []}] * 3})
    assert search.search(1) == [{"title": "", "href": "https://example.org", "body": ""}]


@pytest.mark.parametrize("stage,error", [
    ("get", requests.Timeout("unit-test-token")),
    ("status", requests.HTTPError("unit-test-token")),
    ("json", ValueError("unit-test-token")),
])
def test_failures_are_silent(search, monkeypatch, capsys, stage, error):
    get = mock_http(monkeypatch, {})
    target = {"get": get, "status": get.return_value.raise_for_status, "json": get.return_value.json}[stage]
    target.side_effect = error
    assert search.search() == []
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_limit(search, monkeypatch, limit):
    get = mock_http(monkeypatch, {})
    assert search.search(limit) == []
    get.assert_not_called()


def test_registration_and_config_selection(monkeypatch):
    # Supply package shells to avoid importing unrelated application dependencies.
    for name, path in [
        ("gpt_researcher", ROOT / "gpt_researcher"),
        ("gpt_researcher.retrievers", ROOT / "gpt_researcher/retrievers"),
        ("gpt_researcher.actions", ROOT / "gpt_researcher/actions"),
    ]:
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, name, package)
    package = sys.modules["gpt_researcher.retrievers"]
    init_path = ROOT / "gpt_researcher/retrievers/__init__.py"
    tree = ast.parse(init_path.read_text())
    # Execute the actual export and import nodes for this integration.
    nodes = [node for node in tree.body if
             isinstance(node, ast.ImportFrom) and node.module == "desearch.desearch"
             or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(init_path), "exec"), package.__dict__)
    assert "DesearchSearch" in package.__all__
    from gpt_researcher.actions.retriever import get_retriever, get_retrievers
    from gpt_researcher.retrievers.utils import get_all_retriever_names, VALID_RETRIEVERS
    assert "desearch" in get_all_retriever_names()
    assert "desearch" in VALID_RETRIEVERS
    # Exercise the real config parser without loading LLM dependencies.
    config_path = ROOT / "gpt_researcher/config/config.py"
    config_tree = ast.parse(config_path.read_text())
    cls = next(node for node in config_tree.body if isinstance(node, ast.ClassDef) and node.name == "Config")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "parse_retrievers")
    namespace = {"List": list, "__name__": "gpt_researcher.config.config", "__package__": "gpt_researcher.config"}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(config_path), "exec"), namespace)
    monkeypatch.setenv("RETRIEVER", "desearch")
    import os
    names = namespace["parse_retrievers"](None, os.environ["RETRIEVER"])
    cfg = types.SimpleNamespace(retrievers=names)
    assert get_retriever("desearch") is package.DesearchSearch
    assert get_retrievers({}, cfg) == [package.DesearchSearch]
