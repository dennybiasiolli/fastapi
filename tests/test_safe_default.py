"""Tests for _safe_default: immutable defaults returned by identity, mutable ones deepcopied."""

from copy import deepcopy

import pytest
from fastapi import FastAPI, Header, Query
from fastapi.dependencies.utils import _IMMUTABLE_TYPES, _safe_default
from fastapi.testclient import TestClient


# --- Unit tests for _safe_default ---


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        0,
        42,
        -1,
        3.14,
        0.0,
        "",
        "hello",
        b"",
        b"bytes",
    ],
    ids=lambda v: f"{type(v).__name__}({v!r})",
)
def test_immutable_returned_by_identity(value):
    """Immutable defaults must be returned without copying (same object)."""
    result = _safe_default(value)
    assert result is value


@pytest.mark.parametrize(
    "value",
    [
        [],
        [1, 2, 3],
        {},
        {"a": 1},
        set(),
        {1, 2},
        [{"nested": [1]}],
    ],
    ids=lambda v: f"{type(v).__name__}({v!r})",
)
def test_mutable_deepcopied(value):
    """Mutable defaults must be deepcopied so mutations don't leak."""
    result = _safe_default(value)
    assert result == value
    assert result is not value


@pytest.mark.parametrize(
    "value",
    [
        (),
        (1, 2, 3),
        ([1, 2], "mixed"),
        frozenset(),
        frozenset({1, 2}),
    ],
    ids=lambda v: f"{type(v).__name__}({v!r})",
)
def test_containers_not_in_fast_path(value):
    """tuple and frozenset are NOT in the immutable fast-path because they
    can contain mutable elements. They go through deepcopy, which may or may
    not return the same object depending on contents (Python optimizes
    all-immutable tuples). The critical invariant: inner mutable data is safe."""
    result = _safe_default(value)
    assert result == value


def test_mutable_list_mutation_safety():
    """Mutating the returned list must not affect the original."""
    original = [1, 2, 3]
    result = _safe_default(original)
    result.append(4)
    assert original == [1, 2, 3]


def test_mutable_dict_mutation_safety():
    """Mutating the returned dict must not affect the original."""
    original = {"key": "value"}
    result = _safe_default(original)
    result["new"] = "added"
    assert "new" not in original


def test_nested_mutable_deepcopied():
    """Nested mutable structures must be fully deepcopied."""
    original = {"items": [1, 2, {"nested": True}]}
    result = _safe_default(original)
    result["items"][2]["nested"] = False
    assert original["items"][2]["nested"] is True


def test_tuple_with_mutable_contents_deepcopied():
    """A tuple containing mutable objects must be deepcopied to prevent inner mutation."""
    original = ([1, 2], [3, 4])
    result = _safe_default(original)
    result[0].append(99)
    assert original[0] == [1, 2]


# --- Integration tests: optional params still resolve correctly ---


app = FastAPI()


@app.get("/search")
async def search(
    q: str | None = None,
    page: int = 1,
    size: int = 10,
    sort: str | None = None,
    order: str | None = None,
    tags: str = "default",
):
    return {
        "q": q,
        "page": page,
        "size": size,
        "sort": sort,
        "order": order,
        "tags": tags,
    }


@app.get("/with-header")
async def with_header(
    x_custom: str | None = Header(default=None),
    x_version: int = Header(default=1),
):
    return {"x_custom": x_custom, "x_version": x_version}


client = TestClient(app)


def test_all_defaults():
    """All optional params use defaults when nothing is provided."""
    response = client.get("/search")
    assert response.status_code == 200
    assert response.json() == {
        "q": None,
        "page": 1,
        "size": 10,
        "sort": None,
        "order": None,
        "tags": "default",
    }


def test_partial_params():
    """Provided params override defaults; missing ones use defaults."""
    response = client.get("/search?q=hello&page=2")
    assert response.status_code == 200
    data = response.json()
    assert data["q"] == "hello"
    assert data["page"] == 2
    assert data["size"] == 10
    assert data["sort"] is None


def test_all_params_provided():
    """When all params provided, no defaults are used."""
    response = client.get("/search?q=x&page=5&size=50&sort=name&order=asc&tags=a")
    assert response.status_code == 200
    assert response.json() == {
        "q": "x",
        "page": 5,
        "size": 50,
        "sort": "name",
        "order": "asc",
        "tags": "a",
    }


def test_header_defaults():
    """Header parameters with defaults work correctly."""
    response = client.get("/with-header")
    assert response.status_code == 200
    assert response.json() == {"x_custom": None, "x_version": 1}


def test_header_provided():
    """Header parameters with explicit values override defaults."""
    response = client.get(
        "/with-header", headers={"x-custom": "test", "x-version": "5"}
    )
    assert response.status_code == 200
    assert response.json() == {"x_custom": "test", "x_version": 5}


def test_defaults_stable_across_requests():
    """Defaults must be consistent across multiple requests (no mutation leakage)."""
    for _ in range(5):
        response = client.get("/search")
        assert response.status_code == 200
        assert response.json()["page"] == 1
        assert response.json()["q"] is None
