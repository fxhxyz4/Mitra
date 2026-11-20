import { createBrowserRouter } from "react-router"
import type { Role } from "@/shared/api"
import type { RouteObject } from "react-router"

import { AppLayout, PublicLayout } from "@/app/layout"
import { ALL_ROLES, HomeRedirect, RequireAuth, RoleGuard, STAFF } from "@/features/auth"
import { NotFoundPage } from "@/pages/not-found"
import { ServerErrorPage } from "@/pages/server-error"
import { paths } from "@/shared/config"
import { PageLoader } from "@/shared/ui"
import { rolesFor } from "./navigation"
import { pages } from "./pages"
import { RouteErrorBoundary } from "./RouteErrorBoundary"

const guarded = (roles: Role[], children: RouteObject[]): RouteObject => ({
  element: <RoleGuard roles={roles} />,
  children,
})

const byNav = (path: string, lazy: RouteObject["lazy"]): RouteObject => guarded(rolesFor(path), [{ path, lazy }])

export const routes: RouteObject[] = [
  {
    Component: PublicLayout,
    HydrateFallback: PageLoader,
    ErrorBoundary: RouteErrorBoundary,
    children: [
      { path: paths.verify, lazy: pages.verify },
      { path: paths.login, lazy: pages.login },
    ],
  },
  {
    path: paths.home,
    Component: AppLayout,
    HydrateFallback: PageLoader,
    children: [
      {
        ErrorBoundary: RouteErrorBoundary,
        children: [
          { path: paths.serverError, Component: ServerErrorPage },
          {
            Component: RequireAuth,
            children: [
              { index: true, Component: HomeRedirect },
              guarded(
                ["EXECUTOR"],
                [
                  { path: paths.my, lazy: pages.my },
                  { path: paths.myMeasure, lazy: pages.measure },
                  { path: paths.myHistory, lazy: pages.myHistory },
                ]
              ),
              guarded(STAFF, [{ path: paths.measure, lazy: pages.measure }]),
              byNav(paths.program, pages.program),
              byNav(paths.review, pages.review),
              byNav(paths.flags, pages.flags),
              byNav(paths.calendar, pages.calendar),
              byNav(paths.reports, pages.reports),
              byNav(paths.integrations, pages.integrations),
              guarded(rolesFor(paths.dashboard), [
                { path: paths.dashboard, lazy: pages.dashboard },
                { path: paths.unit, lazy: pages.unit },
              ]),
              byNav(paths.recommendations, pages.recommendations),
              byNav(paths.analytics, pages.analytics),
              byNav(paths.riskModel, pages.riskModel),
              byNav(paths.risks, pages.risks),
              byNav(paths.audit, pages.audit),
              byNav(paths.adminUsers, pages.adminUsers),
              byNav(paths.adminOrgUnits, pages.adminOrgUnits),
              byNav(paths.adminDictionaries, pages.adminDictionaries),
              byNav(paths.adminSettings, pages.adminSettings),
              guarded(ALL_ROLES, [{ path: "*", Component: NotFoundPage }]),
            ],
          },
        ],
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
