// API types are generated from the backend's OpenAPI schema:
//   pnpm --filter @boutique/api-client generate   (backend running on :8000)
// The generated file lands in src/generated/schema.d.ts.
//
// Feature 10 deliberately did NOT adopt this: the storefront ships its own
// local src/api.ts. Codegen buys drift-proof types but needs a live backend in
// the dev loop and a committed artifact CI can neither regenerate nor verify —
// so it drifts silently, which is the exact failure it was bought to prevent.
// Three read-only GETs with no request body did not justify that.
//
// The generate step now also needs APP_ENV=dev: F10 disabled /openapi.json
// outside dev, because a public storefront origin puts the schema in front of
// crawlers (see create_app in backend/app/main.py).
//
// OWNER: E3 #14 — the booking flow adds mutations with real request bodies,
// which is where codegen starts paying for itself. Hoisting the shared fetch
// helpers out of apps/manage and apps/storefront belongs in that same pass.
export {};
