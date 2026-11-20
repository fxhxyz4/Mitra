const NUM = /\p{Nd}/u
const LINK = /(https?:\/\/|www\.|№\s*\d|наказ|протокол|лист|акт(?![\p{L}\p{N}_])|додаток)/iu
export const SIMILARITY_THRESHOLD = 0.75

const normalize = (text: string) => (text.toLowerCase().match(/[\p{L}\p{N}_]+/gu) ?? []).join(" ")

type Range = { alo: number; ahi: number; blo: number; bhi: number }

function longestMatch(a: string[], b: string[], b2j: Map<string, number[]>, { alo, ahi, blo, bhi }: Range) {
  let besti = alo
  let bestj = blo
  let bestsize = 0
  let j2len = new Map<number, number>()
  for (let i = alo; i < ahi; i++) {
    const next = new Map<number, number>()
    for (const j of b2j.get(a[i] ?? "") ?? []) {
      if (j < blo) continue
      if (j >= bhi) break
      const k = (j2len.get(j - 1) ?? 0) + 1
      next.set(j, k)
      if (k > bestsize) {
        besti = i - k + 1
        bestj = j - k + 1
        bestsize = k
      }
    }
    j2len = next
  }
  while (besti > alo && bestj > blo && a[besti - 1] === b[bestj - 1]) {
    besti--
    bestj--
    bestsize++
  }
  while (besti + bestsize < ahi && bestj + bestsize < bhi && a[besti + bestsize] === b[bestj + bestsize]) bestsize++
  return { i: besti, j: bestj, size: bestsize }
}

export function sequenceRatio(left: string, right: string) {
  const a = Array.from(left)
  const b = Array.from(right)
  if (a.length + b.length === 0) return 1
  const b2j = new Map<string, number[]>()
  b.forEach((ch, j) => {
    const list = b2j.get(ch)
    if (list) list.push(j)
    else b2j.set(ch, [j])
  })
  if (b.length >= 200) {
    const limit = Math.floor(b.length / 100) + 1
    for (const [ch, list] of [...b2j]) if (list.length > limit) b2j.delete(ch)
  }
  let matches = 0
  const queue: Range[] = [{ alo: 0, ahi: a.length, blo: 0, bhi: b.length }]
  for (let r = queue.pop(); r; r = queue.pop()) {
    const { i, j, size } = longestMatch(a, b, b2j, r)
    if (!size) continue
    matches += size
    if (r.alo < i && r.blo < j) queue.push({ alo: r.alo, ahi: i, blo: r.blo, bhi: j })
    if (i + size < r.ahi && j + size < r.bhi) queue.push({ alo: i + size, ahi: r.ahi, blo: j + size, bhi: r.bhi })
  }
  return (2 * matches) / (a.length + b.length)
}

export const similarity = (a: string, b: string) => Math.round(sequenceRatio(normalize(a), normalize(b)) * 100) / 100

export function resultHints(title: string, description: string, requiredEvidence: string, evidenceCount: number) {
  const hints: string[] = []
  const text = description.trim()
  if (text) {
    if (similarity(title, text) >= SIMILARITY_THRESHOLD)
      hints.push("Опис результату майже повторює назву заходу — опишіть, що саме змінилось.")
    if (!NUM.test(text) && !LINK.test(text))
      hints.push("Додайте вимірюваний показник (число) або посилання на документ (№ наказу, протоколу).")
  }
  if (requiredEvidence && evidenceCount === 0) hints.push(`Потрібні підтвердні матеріали: ${requiredEvidence}`)
  return hints
}
