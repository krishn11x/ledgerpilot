# Generated API client

`generated.ts` in this directory is produced from the FastAPI OpenAPI schema and
is **gitignored** -- never edit it by hand.

Start the backend, then:

```bash
npm run api:generate
```

This is the mechanism that keeps the two halves of the app in sync: request and
response types are derived from the Python Pydantic models, so a backend change
that breaks the frontend fails at `tsc` rather than at runtime in front of an
audience.
