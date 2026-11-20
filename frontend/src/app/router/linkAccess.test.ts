import { describe, expect, it } from "vitest"

import { paths } from "@/shared/config"
import { LINKED_PAGES } from "@/shared/ui/pageAccess"
import { rolesFor } from "./navigation"

describe("links to records", () => {
  it("open only pages the role is let into by the router", () => {
    for (const path of [
      paths.riskModel,
      paths.flags,
      paths.recommendations,
      paths.reports,
    ])
      expect([...(LINKED_PAGES[path] ?? [])].sort(), path).toEqual([...rolesFor(path)].sort())
  })
})
