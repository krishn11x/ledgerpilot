"""HTTP surface.

This package contains **no business logic**. Routers validate input, call into
the library, and serialise the result. That constraint keeps two things true:
the whole system stays runnable from ``cli.py`` when the frontend is broken,
and every layer below stays testable without HTTP.

The API contract is generated, not hand-maintained: domain Pydantic models flow
into FastAPI, out as OpenAPI, and into TypeScript via ``openapi-typescript``.
Frontend/backend drift becomes a compile error instead of a runtime surprise.
"""
