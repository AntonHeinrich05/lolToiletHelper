// Root flat config: the browser-extension and tooling scripts outside /frontend (which has its own config).
module.exports = [
  { ignores: ["frontend/**", "**/node_modules/**", "downloads/**", "original/**", "**/.venv/**", "**/.expo/**"] },
  {
    files: ["autopicker/**/*.js", "tools/**/*.js", "tests/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        browser: "readonly", chrome: "readonly", globalThis: "readonly", console: "readonly",
        setTimeout: "readonly", clearTimeout: "readonly", setInterval: "readonly", clearInterval: "readonly",
        URL: "readonly", URLSearchParams: "readonly", Promise: "readonly", TextEncoder: "readonly", TextDecoder: "readonly",
        module: "writable", require: "readonly", process: "readonly", __dirname: "readonly", structuredClone: "readonly",
      },
    },
    rules: {},
  },
];
