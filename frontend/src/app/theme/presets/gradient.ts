import { graphitePreset } from "./graphite"
import { pastel } from "./pastel.palette"
import type { ThemePreset } from "./types"

const meshLight = [
  "radial-gradient(at 0% 0%, #b9def0 0, transparent 55%)",
  "radial-gradient(at 100% 15%, #f2c9db 0, transparent 50%)",
  "radial-gradient(at 15% 100%, #d6cff6 0, transparent 50%)",
  "radial-gradient(at 95% 100%, #f7e3b0 0, transparent 55%)",
  `linear-gradient(160deg, ${pastel.sky} 0%, ${pastel.lavender} 35%, ${pastel.rose} 65%, ${pastel.sand} 100%)`,
].join(", ")

const meshDark = [
  "radial-gradient(at 0% 0%, rgb(56 150 196 / 0.55) 0, transparent 55%)",
  "radial-gradient(at 100% 15%, rgb(196 72 128 / 0.45) 0, transparent 50%)",
  "radial-gradient(at 15% 100%, rgb(112 92 214 / 0.5) 0, transparent 55%)",
  "radial-gradient(at 95% 100%, rgb(200 150 40 / 0.35) 0, transparent 55%)",
  "linear-gradient(160deg, #10202a 0%, #1a1530 40%, #2a1424 70%, #241c0e 100%)",
].join(", ")

export const gradientPreset: ThemePreset = {
  id: "gradient",
  label: "Градієнт",
  swatches: [
    "#8fd0ea",
    "#b3a8f5",
    "#f19bbf",
    "#f7d77f",
  ],
  browserColor: { light: "#d8eef6", dark: "#151618" },
  theme: graphitePreset.theme,
  cssVariablesResolver: theme => {
    const base = graphitePreset.cssVariablesResolver(theme)
    return {
      variables: { ...base.variables, "--app-card-glass": "1" },
      light: {
        ...base.light,
        "--app-page-bg": meshLight,
        "--app-navbar-bg": "rgb(255 255 255 / 0.4)",
        "--app-surface-glass": "rgb(255 255 255 / 0.45)",
        "--app-card-bg": "rgb(255 255 255 / 0.68)",
        "--app-card-border": "rgb(255 255 255 / 0.8)",
      },
      dark: {
        ...base.dark,
        "--app-page-bg": meshDark,
        "--app-navbar-bg": "rgb(14 15 18 / 0.45)",
        "--app-surface-glass": "rgb(14 15 18 / 0.5)",
        "--app-card-bg": "rgb(22 23 27 / 0.62)",
        "--app-card-border": "rgb(255 255 255 / 0.08)",
      },
    }
  },
}
