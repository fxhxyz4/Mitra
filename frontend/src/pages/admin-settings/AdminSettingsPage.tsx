import { SimpleGrid } from "@mantine/core"

import { AiSettingsCard } from "@/features/admin"
import { PageHeader, Seo } from "@/shared/ui"

export function AdminSettingsPage() {
  return (
    <>
      <Seo title='Налаштування' />
      <PageHeader
        title='Налаштування'
        description='Параметри системи для всіх користувачів'
      />
      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        <AiSettingsCard />
      </SimpleGrid>
    </>
  )
}
