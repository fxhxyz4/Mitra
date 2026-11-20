import {
  IconAlertTriangle,
  IconBook2,
  IconBuildingCommunity,
  IconBulb,
  IconCalendarTime,
  IconChartLine,
  IconChecklist,
  IconClipboardCheck,
  IconFileAnalytics,
  IconFlag,
  IconHistory,
  IconLayoutDashboard,
  IconListCheck,
  IconPlugConnected,
  IconScale,
  IconSettings,
  IconShieldLock,
  IconUsers,
} from "@tabler/icons-react"
import type { Role } from "@/shared/api"
import type { Icon } from "@tabler/icons-react"

import { paths } from "@/shared/config"
import { pages } from "./pages"

export type NavItem = {
  to: string
  label: string
  icon: Icon
  load: () => Promise<unknown>
  roles: Role[]
  group: string
}

export const navigation: NavItem[] = [
  { to: paths.my, label: "Мої заходи", icon: IconChecklist, load: pages.my, roles: ["EXECUTOR"], group: "Моя робота" },
  {
    to: paths.myHistory,
    label: "Історія і зауваження",
    icon: IconHistory,
    load: pages.myHistory,
    roles: ["EXECUTOR"],
    group: "Моя робота",
  },
  {
    to: paths.dashboard,
    label: "Executive Dashboard",
    icon: IconLayoutDashboard,
    load: pages.dashboard,
    roles: ["HEAD", "ANALYST"],
    group: "Управління",
  },
  {
    to: paths.recommendations,
    label: "Рекомендації",
    icon: IconBulb,
    load: pages.recommendations,
    roles: [
      "HEAD",
      "COORDINATOR",
      "ANALYST",
    ],
    group: "Управління",
  },
  {
    to: paths.program,
    label: "Паспорт програми",
    icon: IconListCheck,
    load: pages.program,
    roles: [
      "COORDINATOR",
      "HEAD",
      "ANALYST",
    ],
    group: "Програма і контроль",
  },
  {
    to: paths.risks,
    label: "Реєстр ризиків",
    icon: IconAlertTriangle,
    load: pages.risks,
    roles: [
      "COORDINATOR",
      "HEAD",
      "ANALYST",
    ],
    group: "Програма і контроль",
  },
  {
    to: paths.review,
    label: "Черга на перевірку",
    icon: IconClipboardCheck,
    load: pages.review,
    roles: ["COORDINATOR"],
    group: "Програма і контроль",
  },
  {
    to: paths.flags,
    label: "Risk Flags",
    icon: IconFlag,
    load: pages.flags,
    roles: [
      "COORDINATOR",
      "HEAD",
      "ANALYST",
    ],
    group: "Програма і контроль",
  },
  {
    to: paths.calendar,
    label: "Контрольні строки",
    icon: IconCalendarTime,
    load: pages.calendar,
    roles: ["COORDINATOR", "ANALYST"],
    group: "Програма і контроль",
  },
  {
    to: paths.reports,
    label: "Звіт НАЗК",
    icon: IconFileAnalytics,
    load: pages.reports,
    roles: ["COORDINATOR", "ANALYST"],
    group: "Програма і контроль",
  },
  {
    to: paths.integrations,
    label: "Інтеграції",
    icon: IconPlugConnected,
    load: pages.integrations,
    roles: ["COORDINATOR"],
    group: "Програма і контроль",
  },
  {
    to: paths.analytics,
    label: "Аналітика",
    icon: IconChartLine,
    load: pages.analytics,
    roles: [
      "EXECUTOR",
      "HEAD",
      "ANALYST",
    ],
    group: "Аналітика",
  },
  {
    to: paths.riskModel,
    label: "Модель ризику",
    icon: IconScale,
    load: pages.riskModel,
    roles: [
      "COORDINATOR",
      "HEAD",
      "ANALYST",
    ],
    group: "Аналітика",
  },
  {
    to: paths.audit,
    label: "Журнал дій",
    icon: IconShieldLock,
    load: pages.audit,
    roles: ["ADMIN"],
    group: "Адміністрування",
  },
  {
    to: paths.adminUsers,
    label: "Користувачі",
    icon: IconUsers,
    load: pages.adminUsers,
    roles: ["ADMIN"],
    group: "Адміністрування",
  },
  {
    to: paths.adminOrgUnits,
    label: "Підрозділи",
    icon: IconBuildingCommunity,
    load: pages.adminOrgUnits,
    roles: ["ADMIN"],
    group: "Адміністрування",
  },
  {
    to: paths.adminDictionaries,
    label: "Довідники",
    icon: IconBook2,
    load: pages.adminDictionaries,
    roles: ["ADMIN"],
    group: "Адміністрування",
  },
  {
    to: paths.adminSettings,
    label: "Налаштування",
    icon: IconSettings,
    load: pages.adminSettings,
    roles: ["ADMIN"],
    group: "Адміністрування",
  },
]

const primaryGroup: Record<Role, string> = {
  EXECUTOR: "Моя робота",
  COORDINATOR: "Програма і контроль",
  HEAD: "Управління",
  ANALYST: "Аналітика",
  ADMIN: "Адміністрування",
}

export function navigationFor(role: Role | null | undefined) {
  if (!role) return []
  const items = navigation.filter(i => i.roles.includes(role))
  const groups = [...new Set(items.map(i => i.group))]
  groups.sort((a, b) => (a === primaryGroup[role] ? -1 : b === primaryGroup[role] ? 1 : 0))
  return groups.map(group => ({ group, items: items.filter(i => i.group === group) }))
}

export const rolesFor = (path: string) => navigation.find(i => i.to === path)?.roles ?? []
