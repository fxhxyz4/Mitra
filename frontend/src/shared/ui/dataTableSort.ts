import type { SortValue } from "./DataTable"

export type SortRule = { key: string; desc?: boolean }

const isEmpty = (v: SortValue) => v === null || v === undefined

export function compareValues(a: SortValue, b: SortValue, desc = false) {
  if (isEmpty(a) || isEmpty(b)) return isEmpty(a) === isEmpty(b) ? 0 : isEmpty(a) ? 1 : -1
  const r = typeof a === "string" && typeof b === "string" ? a.localeCompare(b, "uk") : Number(a) - Number(b)
  return desc ? -r : r
}

export function nextSort(rules: SortRule[], key: string, fresh = false): SortRule[] {
  if (fresh) return [{ key, desc: !(rules.length === 1 && rules[0]!.key === key && rules[0]!.desc) }]
  const at = rules.findIndex(r => r.key === key)
  if (at < 0) return [...rules, { key, desc: true }]
  // спадання → зростання → прибрати зі сортування
  return rules[at]!.desc ? rules.map((r, i) => (i === at ? { key, desc: false } : r)) : rules.filter((_, i) => i !== at)
}
