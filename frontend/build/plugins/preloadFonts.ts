import type { Plugin } from "vite"

export function preloadFonts(patterns: RegExp[]): Plugin {
  return {
    name: "preload-fonts",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(_html, ctx) {
        const files = Object.keys(ctx.bundle ?? {}).filter(f => f.endsWith(".woff2"))
        return patterns
          .map(re => files.find(f => re.test(f)))
          .filter((f): f is string => Boolean(f))
          .map(f => ({
            tag: "link",
            attrs: { rel: "preload", href: `/${f}`, as: "font", type: "font/woff2", crossorigin: "" },
            injectTo: "head" as const,
          }))
      },
    },
  }
}
