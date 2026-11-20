import { useState } from "react"
import { useDebouncedValue } from "@mantine/hooks"

export const SEARCH = {
  debounceMs: 200,
  limit: 50,
  nothingFound: "Нічого не знайдено",
} as const

const normalize = (text: string) => text.toLocaleLowerCase("uk-UA").replace(/ʼ|'|’/g, "").trim()
const splitWords = (text: string) =>
  normalize(text)
    .split(/[\s.,;:·()«»"/\\-]+/)
    .filter(Boolean)

export const isSearchReady = (query: string) => normalize(query).length > 0

export function matchScore(text: string, query: string): number {
  const t = normalize(text)
  const q = normalize(query)
  if (!q) return 0
  if (t === q) return 1000
  const words = splitWords(text)
  const parts = splitWords(query)
  if (!parts.length) return 0
  let score = t.startsWith(q) ? 500 : t.includes(q) ? 200 : 0
  for (const [i, p] of parts.entries()) {
    const at = words.findIndex(w => w.startsWith(p))
    if (at >= 0) score += 60 - Math.min(at, 20) + (i === 0 && at === 0 ? 30 : 0)
    else if (t.includes(p)) score += 20
    else return 0
  }
  return score
}

export function rankByQuery<T>(items: T[], query: string, text: (item: T) => string): T[] {
  if (!isSearchReady(query)) return items
  return items
    .map((item, index) => ({ item, index, score: matchScore(text(item), query) }))
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map(x => x.item)
}

export function useDebouncedSearch(initial = "") {
  const [value, setValue] = useState(initial)
  const [debounced] = useDebouncedValue(value, SEARCH.debounceMs)
  const query = debounced.trim()
  return { value, setValue, debounced, query, pending: value !== debounced }
}
