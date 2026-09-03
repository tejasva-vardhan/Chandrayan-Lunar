"""HTTP application wrapper around the scientific core.

Scientific algorithms live in ``src/``. This package must not reimplement them.
"""

__all__ = ["create_app"]


def create_app():
    from api.app import create_app as _create_app

    return _create_app()
