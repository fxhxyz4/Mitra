import { fireEvent, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { MeasureDraft } from "@/shared/api"

import { session } from "@/shared/api"
import { renderRoutes } from "@/test/render"
import { MeasureForm } from "./MeasureForm"

const draft: MeasureDraft = {
  measure: {
    sectionId: "s2",
    code: "2.9",
    title: "Навчання членів тендерного комітету",
    isPermanent: false,
    plannedDeadline: "2026-12-20",
    riskId: null,
    indicatorText: "Частка членів комітету, що пройшли навчання",
    indicatorUnit: "%",
    indicatorTarget: "100.0000",
    requiredEvidence: "Протокол навчання",
    assignments: [],
  },
  fields: {
    title: { value: "Навчання членів тендерного комітету", source: "document", documentValue: "" },
    plannedDeadline: { value: "2026-12-20", source: "rule", documentValue: "до кінця року" },
  },
  warnings: ["Відповідальний підрозділ не знайдено: оберіть вручну."],
  similar: [{ measureId: "m7", code: "2.3", title: "Навчання з публічних закупівель", score: 0.72 }],
  fileName: "card.docx",
  model: "",
  modelUsed: false,
  disclaimer: "",
}

const sections = [
  { id: "s1", number: 1 },
  { id: "s2", number: 2 },
]

const renderForm = (props: Partial<Parameters<typeof MeasureForm>[0]> = {}) =>
  renderRoutes([
    {
      path: "/",
      element: (
        <MeasureForm
          opened
          onClose={() => {}}
          sections={sections}
          programId='p1'
          {...props}
        />
      ),
    },
  ])

describe("MeasureForm", () => {
  beforeEach(() => {
    session.set({ id: "u1", displayName: "Координатор", role: "COORDINATOR", orgUnitId: "o1" })
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }))
    )
  })

  afterEach(() => {
    session.clear()
    vi.unstubAllGlobals()
  })

  it("offers the measure card drop zone for a new measure", async () => {
    renderForm()
    expect(await screen.findByText(/заповнити з картки заходу/i)).toBeInTheDocument()
  })

  it("prefills the form from a document draft with sources", async () => {
    renderForm({ draft })
    expect(await screen.findByDisplayValue("Навчання членів тендерного комітету")).toBeInTheDocument()
    expect(screen.getByDisplayValue("2.9")).toBeInTheDocument()
    expect(screen.getByText(/заповнено з документа «card.docx»/i)).toBeInTheDocument()
    expect(screen.getByText("З документа")).toBeInTheDocument()
    expect(screen.getByText("За правилом")).toBeInTheDocument()
    expect(screen.getByText(/у документі: «до кінця року»/i)).toBeInTheDocument()
    expect(screen.getByText(/відповідальний підрозділ не знайдено/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /2\.3 — навчання з публічних закупівель/i })).toBeInTheDocument()
    expect(screen.queryByText(/заповнити з картки заходу/i)).not.toBeInTheDocument()
  })

  it("clears the draft", async () => {
    renderForm({ draft })
    fireEvent.click(await screen.findByRole("button", { name: /очистити форму/i }))
    expect(screen.queryByDisplayValue("Навчання членів тендерного комітету")).not.toBeInTheDocument()
    expect(screen.getByText(/заповнити з картки заходу/i)).toBeInTheDocument()
  })
})
