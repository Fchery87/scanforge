# ADR-008: openapi-typescript + Zod for API type safety

## Status
Accepted

## Decision
Generate TypeScript types from the FastAPI OpenAPI spec using `openapi-typescript@7` and add Zod runtime validation at the API fetch boundary.

## Rationale
The web codebase used `any` for most API response types, making it invisible when the API shape changed. Two-layer enforcement:

1. **Compile-time (openapi-typescript)**: `apps/api/scripts/emit_openapi.py` generates `apps/api/openapi.json` from the live FastAPI app. CI fails if the committed spec diverges from the app definition. `npm run gen:types` regenerates `apps/web/lib/api-types.ts`. CI fails if the committed types diverge from the spec.

2. **Runtime (Zod)**: `apps/web/lib/api-schemas.ts` defines schemas for `Organization`, `Scan`, and `Finding` responses. The `request()` wrapper accepts an optional `ZodType<T>` and calls `safeParse` on responses. On mismatch, a structured `console.error` is emitted and the raw data is returned — the app stays up but the schema drift is visible in browser logs.

`openapi-typescript` was chosen over Hey API because it produces a single self-contained types file with zero runtime footprint. Hey API is a full client generator with more opinions; openapi-typescript is closer to a type-level codegen primitive.

## Consequences
- `openapi.json` must be regenerated whenever a Pydantic model changes (CI enforces this)
- `api-types.ts` is committed and ~5 000 lines; it is not hand-edited
- Full migration of `api.ts` call sites to use generated types is a follow-up; current work applies Zod validation to the three most critical list endpoints
