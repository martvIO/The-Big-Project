// API types are generated from the backend's OpenAPI schema:
//   pnpm --filter @boutique/api-client generate   (backend running on :8000)
// The generated file lands in src/generated/schema.d.ts.
//
// Feature 10 deliberately did NOT adopt this: the storefront ships its own
// local src/api.ts. Codegen buys drift-proof types but needs a live backend in
// the dev loop and a committed artifact CI can neither regenerate nor verify —
// so it drifts silently, which is the exact failure it was bought to prevent.
// Hoisting the shared fetch helpers out of apps/manage is a deferred cleanup.
export {};
