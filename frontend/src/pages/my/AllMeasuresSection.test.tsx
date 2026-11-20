import { useState } from "react"
import { fireEvent, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { MeasureListItem, MeasureStatus } from "@/shared/api"

import { session } from "@/shared/api"
import { renderRoutes } from "@/test/render"
import { AllMeasuresSection } from "./AllMeasuresSection"
import type { MeasureFilter } from "./AllMeasuresSection"

const item = (
  id: string,
  code: string,
  status: MeasureStatus | null,
  deadline: string,
  isOverdue = false
): MeasureListItem => ({
  id,
  code,
  title: `Захід ${code}`,
  sectionNumber: 1,
  isPermanent: false,
  plannedDeadline: deadline,
  deadline,
  period: "2026-H2",
  status,
  isOverdue,
  daysLeft: 100,
  risk: null,
  responsibleUnit: null,
  responsibleUser: null,
  openFlags: [],
  evidenceCount: 0,
})

// строки далеко за 30 днів і завершені — саме ті, що на сторінці «Мої заходи» раніше ніде не з'являлись
const mine = [
  item("m1", "1.5", "NOT_DONE", "2026-04-30"),
  item("m2", "2.10", "IN_PROGRESS", "2026-10-31"),
  item("m3", "1.2", "IN_PROGRESS", "2026-12-31"),
  item("m4", "2.3", "DONE", "2026-06-30"),
  item("m5", "3.1", "ON_REVIEW", "2026-12-31"),
  item("m6", "3.2", null, "2026-12-31"),
  item("m7", "1.9", "IN_PROGRESS", "2026-06-30", true),
  item("m8", "2.7", "RETURNED", "2026-12-01"),
]

function Page() {
  const [filter, setFilter] = useState<MeasureFilter>("all")
  return (
    <AllMeasuresSection
      filter={filter}
      onFilterChange={setFilter}
      comments={{ m8: "Додайте протокол засідання" }}
    />
  )
}

const codes = () => screen.getAllByRole("link").map(a => within(a).getByText(/^\d+\.\d+$/).textContent)

describe("AllMeasuresSection", () => {
  beforeEach(() => {
    session.set({ id: "u1", displayName: "Виконавець", role: "EXECUTOR", orgUnitId: "o1" })
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(mine), { headers: { "Content-Type": "application/json" } }))
    )
    renderRoutes([{ path: "/", element: <Page /> }])
  })
  afterEach(() => {
    session.clear()
    vi.unstubAllGlobals()
  })

  it("lists every measure of the executor, work in progress first, and opens it on their page", async () => {
    expect(await screen.findByText("Усі мої заходи (8)")).toBeInTheDocument()
    expect(codes()).toEqual([
      "1.9",
      "2.7",
      "2.10",
      "1.2",
      "3.2",
      "3.1",
      "2.3",
      "1.5",
    ]) // overdue, returned, the rest
    expect(screen.getByRole("link", { name: /Захід 1\.5/ })).toHaveAttribute("href", "/my/measures/m1")
  })

  it("filters done, not done and the rest", async () => {
    await screen.findByText("Усі мої заходи (8)")
    fireEvent.click(screen.getByText("Виконані 1"))
    expect(codes()).toEqual(["2.3"])
    fireEvent.click(screen.getByText("Не виконані 1"))
    expect(codes()).toEqual(["1.5"])
    fireEvent.click(screen.getByText("На перевірці 1"))
    expect(codes()).toEqual(["3.1"])
    fireEvent.click(screen.getByText("Прострочені 1"))
    expect(codes()).toEqual(["1.9"])
    fireEvent.click(screen.getByText("Повернені 1"))
    expect(codes()).toEqual(["2.7"])
    expect(screen.getByText("Додайте протокол засідання")).toBeInTheDocument() // the coordinator's comment
    fireEvent.click(screen.getByText("В роботі 5"))
    expect(codes()).toEqual([
      "1.9",
      "2.7",
      "2.10",
      "1.2",
      "3.2",
    ])
  })
})
