import { screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import type { Role, SourceRef } from "@/shared/api"

import { session } from "@/shared/api"
import { renderRoutes } from "@/test/render"
import { ReferencedText } from "./ReferencedText"

const refs: SourceRef[] = [
  { n: 1, type: "risk", id: "r1", label: "Ризик KR04", target: "m2" },
  { n: 2, type: "flag", id: "f1", label: "Прапорець R1 заходу 2.3", target: "m1" },
  { n: 3, type: "signal", id: "s1", label: "Сигнал D1 ризику KR04", target: "r1" },
  { n: 4, type: "measure", id: "m1", label: "Захід 2.3" },
]

const hrefOf = (name: string) => screen.queryByRole("link", { name })?.getAttribute("href") ?? null

const as = (role: Role) => {
  session.set({ id: "u1", displayName: role, role, orgUnitId: "o1" })
  renderRoutes([
    {
      path: "/",
      element: (
        <ReferencedText
          text='[1] [2] [3] [4]'
          references={refs}
        />
      ),
    },
  ])
}

describe("ReferencedText links", () => {
  afterEach(() => session.clear())

  it.each([
    "COORDINATOR",
    "HEAD",
    "ANALYST",
  ] as Role[])("%s: risk and signal open the risk model", role => {
    as(role)
    expect(hrefOf("Ризик KR04")).toBe("/risk-model?risk=r1")
    expect(hrefOf("Сигнал D1 ризику KR04")).toBe("/risk-model?risk=r1")
    expect(hrefOf("Прапорець R1 заходу 2.3")).toBe("/measures/m1")
    expect(hrefOf("Захід 2.3")).toBe("/measures/m1")
  })

  it("EXECUTOR: everything opens on their own measure pages, nothing sends them home", () => {
    as("EXECUTOR")
    expect(hrefOf("Ризик KR04")).toBe("/my/measures/m2")
    expect(hrefOf("Прапорець R1 заходу 2.3")).toBe("/my/measures/m1")
    expect(hrefOf("Захід 2.3")).toBe("/my/measures/m1")
    expect(hrefOf("Сигнал D1 ризику KR04")).toBeNull()
    expect(screen.getAllByText("Сигнал D1 ризику KR04").length).toBeGreaterThan(0)
  })

  it("ADMIN: no subject pages at all, so no links", () => {
    as("ADMIN")
    for (const r of refs) expect(hrefOf(r.label)).toBeNull()
  })
})
