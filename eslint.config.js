const tsParser = require("@typescript-eslint/parser");
const tsPlugin = require("@typescript-eslint/eslint-plugin");

module.exports = [
  {
    ignores: ["**/*.min.js", "**/*.min.css", "**/bootstrap-icons/**"],
  },
  {
    files: ["app/**/static/**/*.ts"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: "./tsconfig.json",
        tsconfigRootDir: __dirname,
      },
      ecmaVersion: "latest",
      sourceType: "script",
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        localStorage: "readonly",
        fetch: "readonly",
        navigator: "readonly",
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
    },
    rules: {
      "no-console": "warn",
      "@typescript-eslint/await-thenable": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": [
        "error",
        { checksVoidReturn: false },
      ],
      "@typescript-eslint/no-unsafe-argument": "error",
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-call": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
      "@typescript-eslint/no-unsafe-return": "error",
    },
  },
];
