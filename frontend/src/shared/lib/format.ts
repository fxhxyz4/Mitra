const numberFmt = new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 2 })
const dateFmt = new Intl.DateTimeFormat("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric" })
const dateTimeFmt = new Intl.DateTimeFormat("uk-UA", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
})

const toDate = (value: string) => new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value)

export const formatNumber = (value: number | string | null | undefined) =>
  value === null || value === undefined || value === "" ? "—" : numberFmt.format(Number(value))

export const formatDate = (value: string | null | undefined) => (value ? dateFmt.format(toDate(value)) : "—")

export const formatDateTime = (value: string | null | undefined) =>
  value ? dateTimeFmt.format(toDate(value.endsWith("Z") || value.includes("+") ? value : `${value}Z`)) : "—"

export const formatPeriod = (period: string | null | undefined) => {
  if (!period) return "—"
  const [year, half] = period.split("-")
  return `${half === "H1" ? "I" : "II"} півріччя ${year}`
}

export const currentPeriod = (date = new Date()) => `${date.getFullYear()}-${date.getMonth() < 6 ? "H1" : "H2"}`

export const formatDaysLeft = (days: number) => {
  if (days === 0) return "сьогодні"
  if (days > 0) return `через ${days} дн.`
  return `${-days} дн. тому`
}

export const formatSize = (bytes: number) =>
  bytes < 1024
    ? `${bytes} Б`
    : bytes < 1024 * 1024
      ? `${(bytes / 1024).toFixed(0)} КБ`
      : `${(bytes / 1024 / 1024).toFixed(1)} МБ`

export const toNumber = (value: string | number | null | undefined) =>
  value === null || value === undefined ? null : Number(value)

export const isoDate = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`
