import type { Role } from "@/shared/api"

import { paths } from "@/shared/config"

const STAFF: Role[] = [
  "COORDINATOR",
  "HEAD",
  "ANALYST",
]

export const LINKED_PAGES: Record<string, Role[]> = {
  [paths.measure]: STAFF,
  [paths.myMeasure]: ["EXECUTOR"],
  [paths.riskModel]: STAFF,
  [paths.flags]: STAFF,
  [paths.recommendations]: STAFF,
  [paths.reports]: ["COORDINATOR", "ANALYST"],
}

export const canOpen = (path: string, role: Role | null | undefined) =>
  Boolean(role && LINKED_PAGES[path]?.includes(role))
