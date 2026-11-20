import { fireEvent, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { RiskAssessment, UncoveredRisk } from "@/shared/api"

import { renderWithProviders } from "@/test/render"
import { RiskMatrix } from "./RiskMatrix"

const risk = (code: string, probability0: number, impact0: number, extra: Partial<RiskAssessment> = {}) =>
  ({
    riskId: code,
    code,
    description: `Ризик ${code}`,
    probability0,
    impact0,
    inherent: probability0 * impact0,
    verdict: "WORKING",
    verdictLabel: "Заходи працюють",
    verdictColor: "green",
    effectLabel: "на траєкторії",
    preliminary: false,
    effectDue: null,
    ...extra,
  }) as RiskAssessment

const uncovered: UncoveredRisk = {
  riskId: "KR14",
  code: "KR14",
  description: "Завищення обсягів ремонтних робіт",
  level: "HIGH",
  probability0: 3,
  impact0: 3,
  inherent: 9,
}

const cellOf = (code: string) => screen.getByText(code).closest("[role='gridcell']") as HTMLElement

describe("RiskMatrix", () => {
  it("puts every risk into its NAZK cell (likelihood × consequences) with the cell level", () => {
    renderWithProviders(
      <RiskMatrix
        risks={[
          risk("KR11", 3, 4, { verdict: "FORMAL", verdictLabel: "Закрито «на папері»", verdictColor: "red" }),
          risk("KR05", 2, 2),
        ]}
        uncovered={[uncovered]}
      />
    )
    expect(screen.getAllByRole("row")).toHaveLength(4) // ймовірність 4…1
    expect(screen.getAllByRole("gridcell")).toHaveLength(16) // 4 × 4
    expect(cellOf("KR11").dataset.level).toBe("CRITICAL") // 3 · 4 = 12
    expect(cellOf("KR11").textContent).toContain("12")
    expect(cellOf("KR05").dataset.level).toBe("MEDIUM") // 2 · 2 = 4
    expect(cellOf("KR14").dataset.level).toBe("HIGH") // ризик без заходів теж на матриці
  })

  it("opens a risk on click", () => {
    const onSelect = vi.fn()
    renderWithProviders(
      <RiskMatrix
        risks={[risk("KR01", 3, 4)]}
        onSelect={onSelect}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: /KR01/ }))
    expect(onSelect).toHaveBeenCalledWith("KR01")
  })
})
