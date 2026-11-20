import { useState } from "react"
import { SegmentedControl, SimpleGrid, Skeleton, Stack } from "@mantine/core"
import type { RecStatus } from "@/shared/api"

import { RecommendationCard, useRecommendations } from "@/features/recommendations"
import { useSession } from "@/shared/api"
import { EmptyState, PageHeader, QueryError, Seo } from "@/shared/ui"

export function RecommendationsPage() {
  const { user } = useSession()
  const [status, setStatus] = useState<RecStatus | "ALL">("PROPOSED")
  const { data, isPending, error } = useRecommendations(status === "ALL" ? undefined : status)
  const sorted = [...(data ?? [])].sort((a, b) => (a.basis.priority ?? 9) - (b.basis.priority ?? 9))

  return (
    <>
      <Seo title='Рекомендації' />
      <PageHeader
        title='Рекомендації'
        description='Сформовані за явними правилами з підставою. Рішення ухвалює керівник: відповідальний і строк або відхилення з коментарем. Прийняту рекомендацію закриває відповідальний або керівник.'
      />
      <QueryError error={error} />
      <Stack gap='md'>
        <SegmentedControl
          w='fit-content'
          value={status}
          onChange={v => setStatus(v as RecStatus | "ALL")}
          data={[
            { value: "PROPOSED", label: "На рішення" },
            { value: "ACCEPTED", label: "Прийняті" },
            { value: "DONE", label: "Виконані" },
            { value: "REJECTED", label: "Відхилені" },
            { value: "ALL", label: "Усі" },
          ]}
        />
        {isPending ? (
          <Skeleton h={240} />
        ) : sorted.length ? (
          <SimpleGrid
            cols={{ base: 1, lg: 2 }}
            spacing='md'
          >
            {sorted.map(r => (
              <RecommendationCard
                key={r.id}
                rec={r}
                canDecide={user?.role === "HEAD"}
              />
            ))}
          </SimpleGrid>
        ) : (
          <EmptyState title='Рекомендацій немає' />
        )}
      </Stack>
    </>
  )
}
