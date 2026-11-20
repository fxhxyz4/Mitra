export const site = {
  name: "Mitra",
  shortName: "Mitra",
  description:
    "Моніторинг виконання антикорупційної програми: заходи, строки, підтвердні матеріали, Risk Flags і звіт за півріччя для Порталу НАЗК.",
  locale: "uk_UA",
  lang: "uk",
  themeColor: { light: "#1144e8", dark: "#141b2b" },
  publicRoutes: ["/login", "/verify"],
  privateRoutes: [
    "/api/",
    "/500",
    "/my",
    "/program",
    "/dashboard",
    "/admin",
  ],
} as const
