import { fireEvent, screen, waitFor, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { AiChat, AiChatMessage, User } from "@/shared/api"

import { renderRoutes } from "@/test/render"
import { ChatPanel } from "./ChatPanel"

const user: User = { id: "u1", displayName: "Керівник", role: "HEAD", orgUnitId: "o1" }

const message = (id: number, role: AiChatMessage["role"], content: string): AiChatMessage => ({
  id,
  role,
  content,
  answerSource: role === "assistant" ? "rule" : null,
  references: role === "assistant" ? [{ n: 1, type: "measure", id: "m1", label: "Захід 2.3" }] : [],
  model: null,
  modelUsed: role === "assistant" ? false : null,
  createdAt: "2026-11-19T10:00:00Z",
})

const chat = (messages: AiChatMessage[]): AiChat => ({
  id: "c1",
  title: "Які заходи прострочені?",
  messageCount: messages.length,
  createdAt: "2026-11-19T10:00:00Z",
  updatedAt: "2026-11-19T10:00:00Z",
  messages,
  disclaimer: "Пропозиція",
})

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })

describe("ChatPanel", () => {
  let calls: string[]
  let thread: AiChatMessage[]

  beforeEach(() => {
    localStorage.clear()
    Element.prototype.scrollIntoView = vi.fn()
    calls = []
    thread = []
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET"
        calls.push(`${method} ${url}`)
        if (method === "DELETE" && url.endsWith("/ai/chats/c1")) {
          thread = []
          return Promise.resolve(new Response(null, { status: 204 }))
        }
        if (method === "POST" && url.endsWith("/ai/chats")) return Promise.resolve(json(chat([]), 201))
        if (method === "POST" && url.endsWith("/ai/chats/c1/messages")) {
          const { question } = JSON.parse(String(init?.body)) as { question: string }
          const n = thread.length
          thread = [
            ...thread,
            message(n + 1, "user", question),
            message(n + 2, "assistant", `Відповідь ${n / 2 + 1} [1]`),
          ]
          return Promise.resolve(json(chat(thread)))
        }
        if (url.endsWith("/ai/chats/c1")) return Promise.resolve(json(chat(thread)))
        if (url.endsWith("/ai/chats")) return Promise.resolve(json(thread.length ? [chat(thread)] : []))
        return Promise.resolve(json({ detail: "not found" }, 404))
      })
    )
  })

  afterEach(() => vi.unstubAllGlobals())

  const ask = (text: string) => {
    fireEvent.change(screen.getByLabelText("Питання по даних"), { target: { value: text } })
    fireEvent.click(screen.getByLabelText("Надіслати"))
  }

  it("creates a chat on the first question and keeps asking in it", async () => {
    renderRoutes([{ path: "/", element: <ChatPanel user={user} /> }])
    expect(screen.getByText("Які ризики зросли?")).toBeInTheDocument()

    ask("Які заходи прострочені?")
    expect(await screen.findByText(/Відповідь 1/)).toBeInTheDocument()
    expect(screen.getByText("Які заходи прострочені?", { selector: "p" })).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByLabelText("Розмова")[0]).toHaveValue("Які заходи прострочені?"))
    expect(screen.queryByText("Які ризики зросли?")).not.toBeInTheDocument()
    expect(localStorage.getItem("mitra.ai-chat.u1")).toContain("c1")

    ask("А хто відповідальний?")
    expect(await screen.findByText(/Відповідь 2/)).toBeInTheDocument()
    expect(screen.getByText("Відповідь 1")).toBeInTheDocument()
    expect(calls.filter(c => c === "POST /api/ai/chats")).toHaveLength(1)
    expect(calls.filter(c => c === "POST /api/ai/chats/c1/messages")).toHaveLength(2)
  })

  it("deletes a chat only after confirmation", async () => {
    thread = [message(1, "user", "Які заходи прострочені?"), message(2, "assistant", "Відповідь 1 [1]")]
    localStorage.setItem("mitra.ai-chat.u1", JSON.stringify("c1"))
    renderRoutes([{ path: "/", element: <ChatPanel user={user} /> }])
    const openDialog = async () => {
      fireEvent.click(await screen.findByLabelText("Дії з розмовою"))
      // the menu fades out under the closing modal, so jsdom still marks it hidden
      fireEvent.click(await screen.findByRole("menuitem", { name: "Видалити", hidden: true }))
      return screen.findByRole("dialog", { name: "Видалити розмову?" })
    }

    fireEvent.click(within(await openDialog()).getByRole("button", { name: "Скасувати" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(calls.some(c => c.startsWith("DELETE"))).toBe(false)

    fireEvent.click(within(await openDialog()).getByRole("button", { name: "Видалити" }))
    await waitFor(() => expect(localStorage.getItem("mitra.ai-chat.u1")).toBe('""'))
    expect(calls.filter(c => c === "DELETE /api/ai/chats/c1")).toHaveLength(1)
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })

  it("reopens the latest chat when none is remembered", async () => {
    thread = [message(1, "user", "Які заходи прострочені?"), message(2, "assistant", "Відповідь 1 [1]")]
    renderRoutes([{ path: "/", element: <ChatPanel user={user} /> }])
    expect(await screen.findByText(/Відповідь 1/)).toBeInTheDocument()
  })

  it("keeps the last chat remembered after starting a new one", async () => {
    thread = [message(1, "user", "Які заходи прострочені?"), message(2, "assistant", "Відповідь 1 [1]")]
    localStorage.setItem("mitra.ai-chat.u1", JSON.stringify("c1"))
    const { unmount } = renderRoutes([{ path: "/", element: <ChatPanel user={user} /> }])
    expect(await screen.findByText(/Відповідь 1/)).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText("Нова розмова"))
    expect(screen.queryByText(/Відповідь 1/)).not.toBeInTheDocument()
    unmount()

    renderRoutes([{ path: "/", element: <ChatPanel user={user} /> }])
    expect(await screen.findByText(/Відповідь 1/)).toBeInTheDocument()
  })

  it("forgets a chat that no longer exists", async () => {
    localStorage.setItem("mitra.ai-chat.u1", JSON.stringify("gone"))
    renderRoutes([{ path: "/", element: <ChatPanel user={user} /> }])
    await waitFor(() => expect(localStorage.getItem("mitra.ai-chat.u1")).toBe('""'))
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })
})
