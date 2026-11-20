export const pages = {
  login: () => import("@/pages/login"),
  verify: () => import("@/pages/verify"),
  my: () => import("@/pages/my"),
  myHistory: () => import("@/pages/my-history"),
  measure: () => import("@/pages/measure"),
  program: () => import("@/pages/program"),
  review: () => import("@/pages/review"),
  flags: () => import("@/pages/flags"),
  calendar: () => import("@/pages/calendar"),
  reports: () => import("@/pages/reports"),
  dashboard: () => import("@/pages/executive"),
  unit: () => import("@/pages/unit"),
  recommendations: () => import("@/pages/recommendations"),
  analytics: () => import("@/pages/analytics"),
  riskModel: () => import("@/pages/risk-model"),
  risks: () => import("@/pages/risks"),
  audit: () => import("@/pages/audit"),
  integrations: () => import("@/pages/integrations"),
  adminUsers: () => import("@/pages/admin-users"),
  adminOrgUnits: () => import("@/pages/admin-org-units"),
  adminDictionaries: () => import("@/pages/admin-dictionaries"),
  adminSettings: () => import("@/pages/admin-settings"),
}

const preloaded = new Set<() => Promise<unknown>>()

export function preload(load: () => Promise<unknown>) {
  if (preloaded.has(load)) return
  preloaded.add(load)
  load().catch(() => preloaded.delete(load))
}
