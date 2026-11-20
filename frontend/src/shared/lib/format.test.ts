import { describe, expect, it } from "vitest"

import { formatDate, formatDaysLeft, formatNumber, formatPeriod } from "./format"
import { resultHints } from "./rules"

const nbsp = (s: string) => s.replace(/\s/g, " ")

describe("format", () => {
  it("formats numbers with uk-UA grouping", () => {
    expect(nbsp(formatNumber(1542))).toBe("1 542")
    expect(formatNumber("35.0000")).toBe("35")
    expect(formatNumber(null)).toBe("—")
  })

  it("formats dates and periods", () => {
    expect(formatDate("2026-10-27")).toBe("27.10.2026")
    expect(formatPeriod("2026-H2")).toBe("II півріччя 2026")
  })

  it("formats days left", () => {
    expect(formatDaysLeft(3)).toBe("через 3 дн.")
    expect(formatDaysLeft(-20)).toBe("20 дн. тому")
  })
})

describe("resultHints", () => {
  it("asks for a number or document reference", () => {
    expect(resultHints("Навчання персоналу", "Проведено навчання", "", 0)).toHaveLength(1)
    expect(resultHints("Навчання персоналу", "Навчено 42 працівники, наказ № 15", "", 0)).toHaveLength(0)
  })

  it("flags descriptions that repeat the title", () => {
    const hints = resultHints("Проведення навчання персоналу", "Проведення навчання персоналу", "", 0)
    expect(hints[0]).toMatch(/повторює назву/)
  })

  it("requires evidence when the measure needs it", () => {
    expect(resultHints("Захід", "Наказ № 5", "Наказ", 0)).toEqual(["Потрібні підтвердні матеріали: Наказ"])
  })
})
