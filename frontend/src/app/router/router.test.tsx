import { screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { RouteObject } from "react-router"

import { session } from "@/shared/api"
import { renderRoutes } from "@/test/render"
import { routes } from "./router"

const login = () => session.set({ id: "u1", displayName: "Координатор", role: "COORDINATOR", orgUnitId: "o1" })

describe("router", () => {
  afterEach(() => {
    session.clear()
    vi.unstubAllGlobals()
  })

  it("redirects guests to login and lists demo accounts from the server", async () => {
    const accounts = [
      { id: "u1", displayName: "Координатор програми", role: "COORDINATOR", orgUnitId: "o1", token: "t" },
    ]
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(accounts), { headers: { "Content-Type": "application/json" } }))
    )
    renderRoutes(routes, "/program")
    expect(await screen.findByRole("heading", { name: /^вхід$/i })).toBeInTheDocument()
    expect(await screen.findByRole("button", { name: /координатор/i })).toBeInTheDocument()
  })

  it("renders 404 for unknown path", async () => {
    login()
    renderRoutes(routes, "/nope/123")
    expect(await screen.findByRole("heading", { name: /сторінку не знайдено/i })).toBeInTheDocument()
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow")
  })

  it("keeps the report verification page public", async () => {
    const { router } = renderRoutes(routes, "/verify")
    expect(await screen.findByRole("heading", { name: /недійсний/i })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/verify")
  })

  it("renders 500 page", async () => {
    renderRoutes(routes, "/500")
    expect(await screen.findByRole("heading", { name: /щось пішло не так/i })).toBeInTheDocument()
  })

  it("keeps executors out of coordinator pages", async () => {
    session.set({ id: "u2", displayName: "Виконавець", role: "EXECUTOR", orgUnitId: "o1" })
    const { router } = renderRoutes(routes, "/review")
    await screen.findByRole("heading", { name: /мої заходи/i })
    expect(router.state.location.pathname).toBe("/my")
  })

  it("catches page crash with error boundary inside layout", async () => {
    login()
    const Crash = () => {
      throw new Error("boom")
    }
    const root = routes.find(r => r.path === "/")!
    const boundary = root.children![0]!
    renderRoutes(
      [
        {
          ...root,
          children: [{ ...boundary, index: undefined, children: [{ path: "/crash", Component: Crash }] }],
        } as RouteObject,
      ],
      "/crash"
    )
    expect(await screen.findByRole("heading", { name: /щось пішло не так/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /паспорт програми/i })).toBeInTheDocument()
  })
})
