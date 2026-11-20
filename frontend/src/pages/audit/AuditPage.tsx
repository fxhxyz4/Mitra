import { useState } from "react"
import { Alert, Button, Group, Select, Stack } from "@mantine/core"
import { IconShieldCheck, IconShieldX } from "@tabler/icons-react"

import { useAuditLog, useVerifyAudit } from "@/features/audit"
import { AuditTimeline } from "@/features/measures"
import { entityLabels } from "@/shared/lib"
import { PageHeader, QueryError, Section, Seo } from "@/shared/ui"

export function AuditPage() {
  const [entity, setEntity] = useState<string | null>(null)
  const log = useAuditLog({ entity: entity ?? undefined })
  const verify = useVerifyAudit()

  return (
    <>
      <Seo title='Журнал дій' />
      <PageHeader
        title='Журнал дій'
        description='Кожна зміна записується зі старим і новим значенням; записи звʼязані ланцюжком хешів'
        actions={
          <Button
            leftSection={<IconShieldCheck size={16} />}
            loading={verify.isPending}
            onClick={() => verify.mutate()}
          >
            Перевірити цілісність
          </Button>
        }
      />
      <QueryError error={log.error} />
      <Stack gap='lg'>
        {verify.data && (
          <Alert
            color={verify.data.ok ? "success" : "danger"}
            icon={verify.data.ok ? <IconShieldCheck size={18} /> : <IconShieldX size={18} />}
            title={verify.data.ok ? "Ланцюжок цілісний" : "Виявлено зміну журналу"}
          >
            Перевірено записів: {verify.data.checked}
            {verify.data.firstBrokenId ? ` · перший пошкоджений запис #${verify.data.firstBrokenId}` : ""}
          </Alert>
        )}
        <Section
          title='Останні 200 записів'
          loading={log.isPending}
          actions={
            <Group>
              <Select
                placeholder='Усі сутності'
                clearable
                value={entity}
                onChange={setEntity}
                data={Object.entries(entityLabels).map(([value, label]) => ({ value, label }))}
                w={220}
              />
            </Group>
          }
        >
          <AuditTimeline entries={log.data} />
        </Section>
      </Stack>
    </>
  )
}
