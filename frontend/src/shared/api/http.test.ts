import { afterEach, describe, expect, it, vi } from "vitest"

import { http, openInTab, parseError, validationMessage } from "./http"

describe("validationMessage", () => {
  it("translates FastAPI validation errors with the field name", () => {
    const item = {
      type: "string_too_short",
      loc: ["body", "comment"],
      msg: "String should have",
      ctx: { min_length: 3 },
    }
    expect(validationMessage(item)).toBe("Коментар: щонайменше 3 симв.")
    expect(validationMessage({ type: "missing", loc: ["body", "dueDate"] })).toBe("Строк: обовʼязкове поле")
    expect(validationMessage({ type: "uuid_parsing", loc: ["body", "responsibleId"] })).toBe(
      "Відповідальний: оберіть значення зі списку"
    )
  })

  it("keeps custom validator text and falls back for unknown fields", () => {
    expect(validationMessage({ type: "value_error", loc: ["body"], msg: "Value error, Строк поза періодом" })).toBe(
      "Строк поза періодом"
    )
    expect(validationMessage({ type: "something_new", loc: ["query", "weeks"] })).toBe("weeks: некоректне значення")
  })
})

describe("parseError", () => {
  it("does not show proxy HTML pages to the user", () => {
    expect(parseError(504, "<html><body><h1>504 Gateway Time-out</h1></body></html>").message).toBe(
      "Сервер не відповів вчасно"
    )
    expect(parseError(500, "<html>oops</html>").message).toBe("Помилка 500")
    expect(parseError(400, "plain text").message).toBe("plain text")
  })
})

describe("AI jobs", () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it("polls a 202 job until it is done and returns its result", async () => {
    vi.useFakeTimers()
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json({ jobId: "j1", status: "queued" }, 202))
      .mockResolvedValueOnce(json({ jobId: "j1", status: "running" }))
      .mockResolvedValueOnce(json({ jobId: "j1", status: "done", result: { text: "готово" } }))
    vi.stubGlobal("fetch", fetch)
    const pending = http<{ text: string }>("/ai/ask", { method: "POST" })
    await vi.runAllTimersAsync()
    await expect(pending).resolves.toEqual({ text: "готово" })
    expect(fetch).toHaveBeenCalledTimes(3)
  })

  it("turns a failed job into an error with the server message", async () => {
    vi.useFakeTimers()
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ jobId: "j2", status: "queued" }), { status: 202 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ jobId: "j2", status: "failed", error: { status: 503, detail: "Мовна модель недоступна" } })
        )
      )
    vi.stubGlobal("fetch", fetch)
    const pending = http("/ai/ask", { method: "POST" })
    const check = expect(pending).rejects.toMatchObject({ status: 503, message: "Мовна модель недоступна" })
    await vi.runAllTimersAsync()
    await check
  })
})

describe("openInTab", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("closes the blank tab when the file cannot be fetched", async () => {
    const tab = { close: vi.fn() }
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Звіт не знайдено" }), { status: 404 }))
    )
    vi.spyOn(window, "open").mockReturnValue(tab as unknown as Window)
    await expect(openInTab("/reports/x/print")).rejects.toThrow("Звіт не знайдено")
    expect(tab.close).toHaveBeenCalled()
  })
})
