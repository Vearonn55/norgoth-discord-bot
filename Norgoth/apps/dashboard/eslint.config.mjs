import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Static assets and vendored bundles — not our source. `public/tinymce`
    // is a copy of the TinyMCE distribution regenerated on every install
    // (see package.json postinstall), so it must never be linted.
    "public/**",
  ]),
  {
    rules: {
      // This rule assumes React Compiler semantics. Every occurrence in this
      // codebase is a legitimate effect — async data fetching, polling,
      // reading localStorage after mount (SSR-safe), or resyncing local draft
      // state when an external store value changes — none of which can avoid
      // calling setState from an effect. Keep it off to avoid false positives.
      "react-hooks/set-state-in-effect": "off",
      // Allow intentional throwaway bindings that are prefixed with `_`
      // (e.g. destructuring to omit a field, or ignored callback args).
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
          destructuredArrayIgnorePattern: "^_",
        },
      ],
    },
  },
]);

export default eslintConfig;
