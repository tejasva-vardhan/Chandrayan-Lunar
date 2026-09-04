"""CORS origin configuration for the HTTP wrapper."""

from __future__ import annotations

from api.app import cors_allow_origins


def test_cors_defaults_include_local_vite_origins() -> None:
    origins = cors_allow_origins(env={})
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins


def test_cors_env_appends_deployed_frontend_origin() -> None:
    origins = cors_allow_origins(
        env={"SIH26166_CORS_ORIGINS": "https://demo.vercel.app, https://other.example"}
    )
    assert origins[0] == "http://localhost:5173"
    assert "https://demo.vercel.app" in origins
    assert "https://other.example" in origins


def test_cors_env_deduplicates_and_ignores_blanks() -> None:
    origins = cors_allow_origins(
        env={"SIH26166_CORS_ORIGINS": "http://localhost:5173, , https://demo.vercel.app"}
    )
    assert origins.count("http://localhost:5173") == 1
    assert "https://demo.vercel.app" in origins
