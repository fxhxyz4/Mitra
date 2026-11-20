import { screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Role } from "@/shared/api"

import { routes } from "@/app/router/router"
import { session } from "@/shared/api"
import { renderRoutes } from "@/test/render"

const verified = {
  valid: true,
  reason: "Підпис дійсний",
  reportId: "rep1",
  period: "2026-H2",
  type: "NAZK",
  programTitle: "Антикорупційна програма",
  orgUnit: "Орган",
  generatedAt: "2026-11-20T10:00:00Z",
  generatedBy: "Координатор програми",
  sha256: "a".repeat(64),
  supersededBy: null,
  supersededAt: null,
  revokedAt: null,
  revokeReason: null,
}

const open = async (role: Role | null) => {
  if (role) session.set({ id: "u1", displayName: role, role, orgUnitId: "o1" })
  renderRoutes(routes, "/verify?id=rep1&h=abc&sig=xyz")
  await screen.findByRole("heading", { name: /файл підписано/i })
}

const button = (name: RegExp) => screen.queryByRole("link", { name }) ?? screen.queryByRole("button", { name })

describe("VerifyPage: the original report", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(verified), { headers: { "Content-Type": "application/json" } }))
    )
  })
  afterEach(() => {
    session.clear()
    vi.unstubAllGlobals()
  })

  it.each(["COORDINATOR", "ANALYST"] as Role[])("%s can open and download it", async role => {
    await open(role)
    expect(button(/відкрити оригінал звіту/i)).toHaveAttribute("href", "/reports?report=rep1")
    expect(button(/завантажити оригінал/i)).toBeInTheDocument()
  })

  it.each([
    "EXECUTOR",
    "HEAD",
    "ADMIN",
  ] as Role[])("%s gets no buttons that would send them home or fail with 403", async role => {
    await open(role)
    expect(button(/відкрити оригінал/i)).toBeNull()
    expect(button(/завантажити оригінал/i)).toBeNull()
    expect(screen.getByText(/доступний координатору й аналітику/i)).toBeInTheDocument()
  })

  it("a guest is offered to sign in", async () => {
    await open(null)
    expect(button(/увійти, щоб відкрити оригінал/i)).toHaveAttribute("href", "/login")
  })
})
