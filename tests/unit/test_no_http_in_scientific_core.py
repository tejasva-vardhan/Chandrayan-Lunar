from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_ROOTS = {
    "fastapi",
    "flask",
    "django",
    "starlette",
    "requests",
    "httpx",
    "aiohttp",
    "uvicorn",
    "sqlalchemy",
    "psycopg",
    "psycopg2",
    "asyncpg",
    "pymongo",
    "redis",
    "boto3",
    "botocore",
}


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_scientific_core_does_not_import_http_libraries() -> None:
    src_root = Path(__file__).resolve().parents[2] / "src"
    offenders: list[str] = []
    for py_file in src_root.rglob("*.py"):
        overlap = _imported_roots(py_file) & FORBIDDEN_ROOTS
        if overlap:
            offenders.append(f"{py_file}: {sorted(overlap)}")
    assert offenders == []
