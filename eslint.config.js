module.exports = [
  {
    ignores: ["**/*.min.js", "**/*.min.css", "**/bootstrap-icons/**"],
  },
  {
    files: ["**/*.js"],
    languageOptions: {
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
    rules: {
      "no-console": "off",
    },
  },
];

