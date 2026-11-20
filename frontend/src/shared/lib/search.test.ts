import { describe, expect, it } from "vitest"

import { isSearchReady, matchScore, rankByQuery } from "./search"

const units = [
  "Управління персоналу",
  "Департамент державних закупівель",
  "Сектор з питань запобігання та виявлення корупції",
  "Відділ закупівель медичного центру",
]
const indicators = [
  "Кількість додаткових угод про збільшення ціни за півріччя, шт.",
  "Кількість учасників тренінгу, осіб",
  "Частка актів виконаних робіт, звірених з дефектними відомостями, %",
]

describe("search", () => {
  it("filters from the first character, without a minimum length", () => {
    expect(isSearchReady("з")).toBe(true)
    expect(rankByQuery(units, "в", u => u)[0]).toBe(units[3])
    expect(rankByQuery(units, "", u => u)).toEqual(units)
  })

  it("matches every typed word in any order", () => {
    expect(rankByQuery(indicators, "кільк угод", i => i)).toEqual([indicators[0]])
    expect(rankByQuery(indicators, "акт дефект", i => i)).toEqual([indicators[2]])
    expect(rankByQuery(indicators, "угод тренінг", i => i)).toEqual([])
  })

  it("ranks prefix matches above word and substring matches", () => {
    expect(matchScore("Департамент закупівель", "деп")).toBeGreaterThan(matchScore("Департамент закупівель", "зак"))
    expect(rankByQuery(units, "закуп", u => u)).toEqual([units[3], units[1]])
    expect(rankByQuery(units, "відділ", u => u)[0]).toBe(units[3])
  })

  it("ignores case and apostrophes", () => {
    expect(matchScore("Імʼя підрозділу", "ІМЯ")).toBeGreaterThan(0)
  })
})
