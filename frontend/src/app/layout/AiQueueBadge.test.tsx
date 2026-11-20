import { act, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { aiQueue } from "@/shared/api"
import { renderWithProviders } from "@/test/render"
import { AiQueueBadge } from "./AiQueueBadge"

describe("AiQueueBadge", () => {
  afterEach(() => act(() => aiQueue.remove("j1")))

  it("shows the queue position and disappears when the job ends", () => {
    renderWithProviders(<AiQueueBadge />)
    expect(screen.queryByText(/ШІ/)).not.toBeInTheDocument()
    act(() => aiQueue.set({ jobId: "j1", status: "queued", ahead: 2 }))
    expect(screen.getByText("ШІ: у черзі 2")).toBeInTheDocument()
    act(() => aiQueue.set({ jobId: "j1", status: "running", ahead: 0 }))
    expect(screen.getByText("ШІ готує відповідь")).toBeInTheDocument()
    act(() => aiQueue.remove("j1"))
    expect(screen.queryByText(/ШІ/)).not.toBeInTheDocument()
  })
})
