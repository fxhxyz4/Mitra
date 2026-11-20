import type { Role } from "@/shared/api"

import { paths } from "@/shared/config"

export const ALL_ROLES: Role[] = [
  "EXECUTOR",
  "COORDINATOR",
  "HEAD",
  "ANALYST",
  "ADMIN",
]
export const STAFF: Role[] = [
  "COORDINATOR",
  "HEAD",
  "ANALYST",
]

export const homeFor = (role: Role | null | undefined): string => {
  switch (role) {
    case "EXECUTOR":
      return paths.my
    case "COORDINATOR":
      return paths.program
    case "HEAD":
      return paths.dashboard
    case "ANALYST":
      return paths.analytics
    case "ADMIN":
      return paths.adminUsers
    default:
      return paths.login
  }
}

export const canManage = (role: Role | null | undefined) => role === "COORDINATOR"
export const isHead = (role: Role | null | undefined) => role === "HEAD"
