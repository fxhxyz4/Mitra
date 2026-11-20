import type { CSSVariablesResolver, MantineThemeOverride } from "@mantine/core"

export type ThemePresetId = "pastel" | "gradient" | "sapphire" | "graphite"

export interface ThemePreset {
  id: ThemePresetId
  label: string
  swatches: string[]
  theme: MantineThemeOverride
  cssVariablesResolver: CSSVariablesResolver
  browserColor: { light: string; dark: string }
}
