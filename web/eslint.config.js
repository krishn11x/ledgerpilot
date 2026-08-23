import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

/**
 * ESLint 9 flat config.
 *
 * Deliberately light: `tsc --noEmit` already covers type correctness, so lint
 * only needs to catch what the compiler can't see -- chiefly the React hook
 * rules, where a violation is a real runtime bug rather than a style opinion.
 */
export default tseslint.config(
  // Never lint generated or built output. `api/generated.ts` is derived from the
  // OpenAPI schema and is not ours to satisfy.
  { ignores: ["dist", "src/api/generated.ts", "node_modules"] },

  js.configs.recommended,
  ...tseslint.configs.recommended,

  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Unused args prefixed with _ are intentional (placeholder signatures).
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },

  // Config files run in Node, not the browser.
  {
    files: ["*.config.{ts,js}"],
    languageOptions: { globals: globals.node },
  },
);
