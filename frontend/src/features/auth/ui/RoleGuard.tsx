import { Navigate, Outlet, useLocation } from "react-router"
import type { Role } from "@/shared/api"

import { useSession } from "@/shared/api"
import { paths } from "@/shared/config"
import { homeFor } from "../model/access"

export function RequireAuth() {
  const { user, manualLogout } = useSession()
  const location = useLocation()
  if (!user)
    return (
      <Navigate
        to={paths.login}
        replace
        state={manualLogout ? null : { from: location.pathname }}
      />
    )
  return <Outlet />
}

export function RoleGuard({ roles }: { roles: Role[] }) {
  const { user } = useSession()
  if (user && !roles.includes(user.role))
    return (
      <Navigate
        to={homeFor(user.role)}
        replace
      />
    )
  return <Outlet />
}

export function HomeRedirect() {
  const { user } = useSession()
  return (
    <Navigate
      to={user ? homeFor(user.role) : paths.login}
      replace
    />
  )
}
