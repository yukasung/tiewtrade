import js from "@eslint/js";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";

export default [
  { ignores: ["dist", "src/api-types.ts", "node_modules", "playwright-report", "test-results"] },
  js.configs.recommended,
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: tsParser,
      parserOptions: { project: "./tsconfig.json", ecmaFeatures: { jsx: true } },
      globals: {
        document: "readonly",
        window: "readonly",
        fetch: "readonly",
        console: "readonly",
        process: "readonly",
        React: "readonly",
      },
    },
    plugins: { "@typescript-eslint": tsPlugin },
    rules: {
      ...tsPlugin.configs["recommended-type-checked"].rules,
      // ห้าม any เพื่อให้ชนิดข้อมูลที่สร้างจากสัญญา API มีผลจริง (P-9)
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
    },
  },
];
