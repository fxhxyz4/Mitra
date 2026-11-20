import { createTheme, defaultVariantColorsResolver, MultiSelect, parseThemeColor, Select } from "@mantine/core"
import type { ComboboxItem, ComboboxParsedItem, OptionsFilter, VariantColorsResolver } from "@mantine/core"

import { matchScore, SEARCH } from "@/shared/lib/search"

const variantColorResolver: VariantColorsResolver = input => {
  const result = defaultVariantColorsResolver(input)
  const color = input.color || input.theme.primaryColor
  const parsed = parseThemeColor({ color, theme: input.theme })
  const isPrimary = parsed.isThemeColor && parsed.color === input.theme.primaryColor && parsed.shade === undefined
  if (input.variant === "filled" && isPrimary) return { ...result, color: "var(--mantine-primary-color-contrast)" }
  return result
}

export const wordsFilter: OptionsFilter = ({ options, search }) => {
  if (!search.trim()) return options
  const rank = (items: ComboboxItem[]) =>
    items
      .map((item, index) => ({ item, index, score: matchScore(item.label, search) }))
      .filter(x => x.score > 0)
      .sort((a, b) => b.score - a.score || a.index - b.index)
      .map(x => x.item)
  return options.flatMap((o): ComboboxParsedItem[] => {
    if (!("group" in o)) return rank([o])
    const items = rank(o.items)
    return items.length ? [{ ...o, items }] : []
  })
}

const searchable = {
  searchable: true,
  filter: wordsFilter,
  nothingFoundMessage: SEARCH.nothingFound,
  maxDropdownHeight: 300,
  comboboxProps: { shadow: "md" },
}

export const baseTheme = createTheme({
  variantColorResolver,
  primaryColor: "brand",
  fontFamily: "'Inter Variable', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  fontFamilyMonospace: "ui-monospace, 'JetBrains Mono', monospace",
  headings: {
    fontWeight: "700",
    sizes: { h1: { fontSize: "clamp(1.5rem, 1.1rem + 1.4vw, 2rem)", lineHeight: "1.2" } },
  },
  cursorType: "pointer",
  respectReducedMotion: true,
  autoContrast: true,
  breakpoints: { xs: "30em", sm: "40em", md: "53.75em", lg: "64em", xl: "90em" },
  components: {
    Select: Select.extend({ defaultProps: searchable }),
    MultiSelect: MultiSelect.extend({ defaultProps: searchable }),
  },
})
