import { fireEvent, screen, within } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { renderWithProviders } from "@/test/render"
import { DataTable } from "./DataTable"
import { nextSort } from "./dataTableSort"
import type { Column } from "./DataTable"

type Row = { id: string; name: string; returns: number | null }

const rows: Row[] = [
  { id: "a", name: "Бета", returns: 2 },
  { id: "b", name: "Альфа", returns: null },
  { id: "c", name: "Гамма", returns: 5 },
]
const columns: Column<Row>[] = [
  { key: "name", label: "Назва", render: r => r.name, sort: r => r.name },
  { key: "returns", label: "Повернень", render: r => r.returns ?? "—", sort: r => r.returns },
]

const names = () =>
  screen
    .getAllByRole("row")
    .slice(1)
    .map(r => within(r).getAllByRole("cell")[0]?.textContent)

describe("DataTable", () => {
  it("sorts by the clicked column, empty values always last", () => {
    renderWithProviders(
      <DataTable
        rows={rows}
        columns={columns}
        rowKey={r => r.id}
        initialSort={{ key: "name", desc: false }}
      />
    )
    expect(names()).toEqual([
      "Альфа",
      "Бета",
      "Гамма",
    ])
    fireEvent.click(screen.getByText("Повернень"))
    expect(names()).toEqual([
      "Гамма",
      "Бета",
      "Альфа",
    ])
    fireEvent.click(screen.getByText("Повернень"))
    expect(names()).toEqual([
      "Бета",
      "Гамма",
      "Альфа",
    ])
  })

  it("reports the clicked row", () => {
    const onRowClick = vi.fn()
    renderWithProviders(
      <DataTable
        rows={rows}
        columns={columns}
        rowKey={r => r.id}
        onRowClick={onRowClick}
      />
    )
    fireEvent.click(screen.getByText("Гамма"))
    expect(onRowClick).toHaveBeenCalledWith(rows[2])
  })
})

describe("DataTable multi-column sort", () => {
  const team: Row[] = [
    { id: "1", name: "Бета", returns: 1 },
    { id: "2", name: "Альфа", returns: 1 },
    { id: "3", name: "Гамма", returns: 3 },
  ]

  it("every header click adds a column to the sort; reset restores the default", () => {
    renderWithProviders(
      <DataTable
        rows={team}
        columns={columns}
        rowKey={r => r.id}
        initialSort={{ key: "name", desc: false }}
      />
    )
    const reset = screen.getByRole("button", { name: /Скинути/ })
    expect(reset).toBeDisabled()
    fireEvent.click(screen.getByText("Повернень"))
    fireEvent.click(screen.getByText("Назва"))
    // повернення ↓, за рівності — назва ↓
    expect(names()).toEqual([
      "Гамма",
      "Бета",
      "Альфа",
    ])
    fireEvent.click(screen.getByText("Назва"))
    // повернення ↓, за рівності — назва ↑
    expect(names()).toEqual([
      "Гамма",
      "Альфа",
      "Бета",
    ])
    expect(reset).toBeEnabled()
    fireEvent.click(reset)
    expect(names()).toEqual([
      "Альфа",
      "Бета",
      "Гамма",
    ])
  })
})

describe("nextSort", () => {
  it("cycles a column in the chain: descending, ascending, removed", () => {
    const a = nextSort([{ key: "x", desc: true }], "y")
    expect(a).toEqual([
      { key: "x", desc: true },
      { key: "y", desc: true },
    ])
    const b = nextSort(a, "y")
    expect(b[1]).toEqual({ key: "y", desc: false })
    expect(nextSort(b, "y")).toEqual([{ key: "x", desc: true }])
    // перший клік замінює сортування за замовчуванням
    expect(nextSort(b, "z", true)).toEqual([{ key: "z", desc: true }])
  })
})
