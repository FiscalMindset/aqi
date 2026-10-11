module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  extends: ["eslint:recommended", "plugin:react-hooks/recommended"],
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  ignorePatterns: ["dist", "node_modules", "playwright-report"],
  rules: {
    "no-restricted-imports": [
      "error",
      {
        paths: [
          {
            name: "ethan",
            message: "The brief forbids contracted anthropic; use AWS Bedrock.",
          },
        ],
      },
    ],
  },
};
