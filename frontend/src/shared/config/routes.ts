export const paths = {
  home: "/",
  login: "/login",
  verify: "/verify",
  my: "/my",
  myMeasure: "/my/measures/:id",
  myHistory: "/my/history",
  program: "/program",
  review: "/review",
  measure: "/measures/:id",
  flags: "/flags",
  calendar: "/calendar",
  reports: "/reports",
  dashboard: "/dashboard",
  unit: "/dashboard/units/:id",
  recommendations: "/recommendations",
  analytics: "/analytics",
  riskModel: "/risk-model",
  risks: "/risks",
  audit: "/audit",
  integrations: "/integrations",
  adminUsers: "/admin/users",
  adminOrgUnits: "/admin/org-units",
  adminDictionaries: "/admin/dictionaries",
  adminSettings: "/admin/settings",
  serverError: "/500",
} as const

export type AppPath = (typeof paths)[keyof typeof paths]

export const withId = (path: string, id: string) => path.replace(":id", id)
