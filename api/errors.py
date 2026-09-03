"""API-layer error mapping. Does not change scientific contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiError(Exception):
    """User-facing API failure with a stable machine code."""

    code: str
    message: str
    status_code: int = 400
    details: dict[str, object] | None = None

    def __str__(self) -> str:
        return self.message


def classify_pipeline_exception(exc: BaseException) -> ApiError:
    """Map scientific/IO exceptions to stable API error codes without stack traces."""

    name = type(exc).__name__
    text = str(exc).strip() or name
    lowered = text.lower()

    if isinstance(exc, FileNotFoundError):
        return ApiError(
            code="missing_input",
            message=text,
            status_code=400,
            details={"exception_type": name},
        )
    if isinstance(exc, TimeoutError):
        return ApiError(
            code="request_timeout",
            message=text,
            status_code=504,
            details={"exception_type": name},
        )
    if "unsupported" in lowered or "unrecognised" in lowered or "unrecognized" in lowered:
        return ApiError(
            code="unsupported_product",
            message=text,
            status_code=400,
            details={"exception_type": name},
        )
    if "metadata" in lowered:
        return ApiError(
            code="missing_metadata",
            message=text,
            status_code=400,
            details={"exception_type": name},
        )
    if isinstance(exc, ValueError):
        return ApiError(
            code="invalid_input",
            message=text,
            status_code=400,
            details={"exception_type": name},
        )
    if isinstance(exc, NotImplementedError):
        return ApiError(
            code="stage_unimplemented",
            message=text,
            status_code=501,
            details={"exception_type": name},
        )
    return ApiError(
        code="backend_exception",
        message=f"{name}: {text}",
        status_code=500,
        details={"exception_type": name},
    )
