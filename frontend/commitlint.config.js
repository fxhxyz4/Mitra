const scopes = [
  "app",
  "pages",
  "home",
  "dashboard",
  "analytics",
  "shared",
  "ui",
  "api",
  "styles",
  "seo",
  "tests",
  "deps",
  "docker",
  "ci",
  "config",
  "release",
]

const aiAttribution = /co-authored-by:.*(claude|anthropic)|claude-session:|generated with \[claude code\]/i

export default {
  extends: ["@commitlint/config-conventional"],
  plugins: [
    {
      rules: {
        "no-ai-attribution": ({ raw }) => [
          !aiAttribution.test(raw ?? ""),
          "commit message must not credit an AI co-author",
        ],
      },
    },
  ],
  rules: {
    "no-ai-attribution": [
      2,
      "always",
    ],
    "type-enum": [
      2,
      "always",
      [
        "feat",
        "fix",
        "perf",
        "refactor",
        "style",
        "test",
        "docs",
        "build",
        "ci",
        "chore",
        "revert",
        "update",
        "hotfix",
      ],
    ],
    "scope-enum": [
      1,
      "always",
      scopes,
    ],
    "subject-case": [0],
    "subject-max-length": [
      2,
      "always",
      72,
    ],
    "header-max-length": [
      2,
      "always",
      100,
    ],
    "body-max-line-length": [
      1,
      "always",
      100,
    ],
  },
  ignores: [message => /^(Merge|Revert) /.test(message)],
}
