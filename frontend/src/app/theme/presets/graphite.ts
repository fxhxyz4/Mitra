import { Badge, Button, Card, Paper, ThemeIcon } from "@mantine/core"

import { graphite, green, ink, lavender, orange, pastel, red } from "./pastel.palette"
import type { ThemePreset } from "./types"

const invertedBrand = {
  "--mantine-color-brand-filled": "#f5f6f7",
  "--mantine-color-brand-filled-hover": "#d4d6da",
  "--mantine-color-brand-light": "rgb(245 246 247 / 0.1)",
  "--mantine-color-brand-light-hover": "rgb(245 246 247 / 0.16)",
  "--mantine-color-brand-light-color": "#f5f6f7",
  "--mantine-color-brand-outline": "#f5f6f7",
  "--mantine-color-brand-outline-hover": "rgb(245 246 247 / 0.08)",
  "--mantine-color-brand-text": "#f5f6f7",
  "--mantine-primary-color-filled": "#f5f6f7",
  "--mantine-primary-color-filled-hover": "#d4d6da",
  "--mantine-primary-color-light": "rgb(245 246 247 / 0.1)",
  "--mantine-primary-color-light-hover": "rgb(245 246 247 / 0.16)",
  "--mantine-primary-color-light-color": "#f5f6f7",
  "--mantine-primary-color-contrast": "#0a0a0b",
}

const dim = (color: string) => `color-mix(in srgb, ${color} 14%, var(--mantine-color-dark-6))`

export const graphitePreset: ThemePreset = {
  id: "graphite",
  label: "Графіт",
  swatches: [
    "#000000",
    "#5f636b",
    "#d4d6da",
    "#ffffff",
  ],
  browserColor: { light: "#f5f6f7", dark: "#151618" },
  theme: {
    colors: { brand: ink, accent: lavender, success: green, warning: orange, danger: red, dark: graphite },
    primaryShade: { light: 9, dark: 6 },
    defaultRadius: "lg",
    radius: { xs: "4px", sm: "8px", md: "12px", lg: "18px", xl: "28px" },
    shadows: {
      xs: "0 1px 2px rgb(0 0 0 / 0.04)",
      sm: "0 2px 8px rgb(0 0 0 / 0.05)",
      md: "0 8px 24px rgb(0 0 0 / 0.08)",
      lg: "0 16px 40px rgb(0 0 0 / 0.1)",
      xl: "0 24px 60px rgb(0 0 0 / 0.12)",
    },
    components: {
      Card: Card.extend({ defaultProps: { withBorder: false, radius: "xl", padding: "xl", shadow: "none" } }),
      Paper: Paper.extend({ defaultProps: { radius: "xl" } }),
      Button: Button.extend({ defaultProps: { radius: "xl" } }),
      Badge: Badge.extend({ defaultProps: { radius: "xl" } }),
      ThemeIcon: ThemeIcon.extend({ defaultProps: { radius: "xl" } }),
    },
  },
  cssVariablesResolver: () => ({
    variables: {
      "--app-header-height": "64px",
      "--app-logo-from": "#000000",
      "--app-logo-to": "#2e3035",
      "--app-logo-mark": "#000000",
      "--app-hero-border": "transparent",
    },
    light: {
      "--mantine-color-body": "#f5f6f7",
      "--mantine-color-text": "#111213",
      "--mantine-color-dimmed": "#4f535a",
      "--app-surface-glass": "rgb(245 246 247 / 0.78)",
      "--app-gradient": "linear-gradient(120deg, #1f6f95 0%, #6b5bd6 50%, #c0457a 100%)",
      "--app-hero-bg": `linear-gradient(120deg, ${pastel.sky} 0%, ${pastel.rose} 35%, ${pastel.lavender} 65%, ${pastel.sand} 100%)`,
      "--app-hero-glow": "0",
      "--app-chart-1": "var(--mantine-color-brand-6)",
      "--app-chart-2": "var(--mantine-color-accent-6)",
      "--app-tint-1": pastel.sky,
      "--app-tint-2": pastel.rose,
      "--app-tint-3": pastel.lavender,
      "--app-tint-4": pastel.sand,
    },
    dark: {
      ...invertedBrand,
      "--mantine-color-body": "#121315",
      "--mantine-color-text": "#f1f2f4",
      "--mantine-color-dimmed": "#b4b7bd",
      "--mantine-color-placeholder": "#8d9199",
      "--mantine-color-default-border": "#3a3c41",
      "--app-surface-glass": "rgb(18 19 21 / 0.82)",
      "--app-gradient": "linear-gradient(120deg, #8fd0ea 0%, #b3a8f5 50%, #f19bbf 100%)",
      "--app-hero-bg": `linear-gradient(120deg, ${dim(pastel.sky)}, ${dim(pastel.rose)} 35%, ${dim(pastel.lavender)} 65%, ${dim(pastel.sand)})`,
      "--app-hero-glow": "0",
      "--app-logo-from": "#f5f6f7",
      "--app-logo-to": "#d4d6da",
      "--app-logo-shield": "#0a0a0b",
      "--app-logo-mark": "#f5f6f7",
      "--app-chart-1": "var(--mantine-color-brand-1)",
      "--app-chart-2": "var(--mantine-color-accent-4)",
      "--app-tint-1": dim(pastel.sky),
      "--app-tint-2": dim(pastel.rose),
      "--app-tint-3": dim(pastel.lavender),
      "--app-tint-4": dim(pastel.sand),
    },
  }),
}
