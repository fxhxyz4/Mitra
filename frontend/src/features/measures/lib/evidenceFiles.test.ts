import { describe, expect, it } from "vitest"

import { appendEvidence, guessDocType, isComplete, toEvidenceFile } from "./evidenceFiles"

const file = (name: string) => new File(["x"], name)

describe("evidence files", () => {
  it("guesses the document type from the file name, otherwise leaves it to the executor", () => {
    expect(guessDocType("Наказ_245.pdf")).toBe("наказ")
    expect(guessDocType("протокол засідання.docx")).toBe("протокол")
    expect(guessDocType("scan_001.jpg")).toBe("")
  })

  it("requires a type and a document date for every file", () => {
    const f = toEvidenceFile(file("акт приймання.pdf"))
    expect(f).toMatchObject({ docType: "акт", documentDate: null })
    expect(isComplete([f])).toBe(false)
    expect(isComplete([{ ...f, documentDate: "2026-06-25" }])).toBe(true)
    expect(isComplete([{ ...f, docType: " ", documentDate: "2026-06-25" }])).toBe(false)
    expect(isComplete([])).toBe(true)
  })

  it("sends files with parallel lists of types and dates", () => {
    const form = new FormData()
    appendEvidence(form, [
      { file: file("a.pdf"), docType: "наказ ", documentDate: "2026-03-01" },
      { file: file("b.pdf"), docType: "акт", documentDate: "2026-03-02" },
    ])
    expect(form.getAll("files")).toHaveLength(2)
    expect(form.getAll("documentTypes")).toEqual(["наказ", "акт"])
    expect(form.getAll("documentDates")).toEqual(["2026-03-01", "2026-03-02"])
  })
})
