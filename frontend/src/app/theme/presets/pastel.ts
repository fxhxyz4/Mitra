import { Badge, Button, Card, DEFAULT_THEME, Paper, ThemeIcon } from "@mantine/core"

import { lavender, pastel, plum, rose } from "./pastel.palette"
import type { ThemePreset } from "./types"

const glow = (color: string, alpha: number) => `color-mix(in srgb, ${color} ${alpha}%, transparent)`

export const pastelPreset: ThemePreset = {
  id: "pastel",
  label: "Пастель",
  swatches: [
    "#8073d9",
    "#ea96b7",
    "#8fd0ea",
    "#9fdcc0",
  ],
  browserColor: { light: "#f4f1fc", dark: "#1f1c31" },
  theme: {
    colors: {
      brand: lavender,
      accent: rose,
      success: DEFAULT_THEME.colors.teal,
      warning: DEFAULT_THEME.colors.orange,
      danger: DEFAULT_THEME.colors.red,
      dark: plum,
    },
    primaryShade: { light: 6, dark: 3 },
    defaultRadius: "lg",
    radius: { xs: "4px", sm: "8px", md: "12px", lg: "18px", xl: "26px" },
    shadows: {
      xs: "0 1px 2px rgb(76 60 160 / 0.06)",
      sm: "0 2px 10px rgb(76 60 160 / 0.08)",
      md: "0 10px 28px rgb(76 60 160 / 0.12)",
      lg: "0 18px 44px rgb(76 60 160 / 0.14)",
      xl: "0 26px 64px rgb(76 60 160 / 0.16)",
    },
    components: {
      Card: Card.extend({ defaultProps: { withBorder: true, radius: "xl", padding: "lg", shadow: "sm" } }),
      Paper: Paper.extend({ defaultProps: { radius: "xl" } }),
      Button: Button.extend({ defaultProps: { radius: "xl" } }),
      Badge: Badge.extend({ defaultProps: { radius: "xl" } }),
      ThemeIcon: ThemeIcon.extend({ defaultProps: { radius: "xl" } }),
    },
  },
  cssVariablesResolver: () => ({
    variables: {
      "--app-header-height": "64px",
      "--app-gradient": "linear-gradient(120deg, #8073d9 0%, #e377a1 55%, #5fb7d9 100%)",
      "--app-logo-from": "#8073d9",
      "--app-logo-to": "#e377a1",
      "--app-logo-mark": "#6b5bd6",
      "--app-kpi-tint": "1",
    },
    light: {
      "--mantine-color-body": "#ffffff",
      "--mantine-color-text": "#1f1c31",
      "--mantine-color-dimmed": "#5b5674",
      "--mantine-color-default-border": "#e6e2f8",
      "--app-page-bg": [
        `radial-gradient(at 0% 0%, ${glow(pastel.lavender, 90)} 0, transparent 50%)`,
        `radial-gradient(at 100% 0%, ${glow(pastel.rose, 90)} 0, transparent 45%)`,
        `radial-gradient(at 50% 100%, ${glow(pastel.sky, 80)} 0, transparent 55%)`,
        "#f7f5fd",
      ].join(", "),
      "--app-navbar-bg": "rgb(247 245 253 / 0.72)",
      "--app-surface-glass": "rgb(255 255 255 / 0.7)",
    },
    dark: {
      "--mantine-color-body": "#1f1c31",
      "--mantine-color-text": "#f1eff9",
      "--mantine-color-dimmed": "#c3bedb",
      "--mantine-color-placeholder": "#9590b3",
      "--mantine-color-anchor": "#ada4ea",
      "--app-on-filled": "#1f1c31",
      "--mantine-color-default-border": "#3d3857",
      "--app-page-bg": [
        "radial-gradient(at 0% 0%, rgb(128 115 217 / 0.28) 0, transparent 50%)",
        "radial-gradient(at 100% 0%, rgb(227 119 161 / 0.2) 0, transparent 45%)",
        "radial-gradient(at 50% 100%, rgb(95 183 217 / 0.16) 0, transparent 55%)",
        "#181628",
      ].join(", "),
      "--app-navbar-bg": "rgb(24 22 40 / 0.72)",
      "--app-surface-glass": "rgb(24 22 40 / 0.72)",
      "--app-logo-mark": "#c1bbec",
    },
  }),
}
