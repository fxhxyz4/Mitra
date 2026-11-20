/* global document, matchMedia */
try {
  var d = document.documentElement
  var s = localStorage.getItem("mantine-color-scheme-value") || "auto"
  if (s === "auto") s = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
  d.setAttribute("data-mantine-color-scheme", s)
  d.setAttribute("data-app-preset", localStorage.getItem("app-theme-preset") || "pastel")
} catch {
  //
}
