"""Uvicorn entrypoint for local development (re-exports api.app:app)."""

from __future__ import annotations

import os

import uvicorn

from api.app import app, create_app

__all__ = ["app", "create_app", "main"]


def main() -> None:
    host = os.environ.get("SIH26166_API_HOST", "127.0.0.1")
    port = int(os.environ.get("SIH26166_API_PORT", "8000"))
    uvicorn.run("api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
