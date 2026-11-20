import { QueryClient } from "@tanstack/react-query"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const isStatic = (key: readonly unknown[]) =>
  key[0] === "ai" ||
  key[0] === "admin" ||
  (key[0] === "reference" && (key[1] === "dictionaries" || key[1] === "org-units"))

export const invalidateDomain = (client: QueryClient = queryClient) =>
  client.invalidateQueries({ predicate: q => !isStatic(q.queryKey) })
