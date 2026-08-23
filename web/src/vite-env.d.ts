/// <reference types="vite/client" />

/**
 * Ambient types for Vite: `import.meta.env`, and treating `.css` imports as
 * modules. Also declares the app's own env vars so a typo in a variable name is
 * a compile error rather than a silent `undefined` at runtime.
 *
 * Note: everything here is public. `VITE_*` values are inlined into the bundle
 * by design, so no secret may ever be declared in this file.
 */
interface ImportMetaEnv {
  /** Absolute API origin. Leave unset in dev to use the Vite proxy at /api. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
