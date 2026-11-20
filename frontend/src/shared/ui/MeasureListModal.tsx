import { useState } from "react"
import { Group, Modal, ScrollArea, Text, TextInput } from "@mantine/core"
import { IconSearch } from "@tabler/icons-react"
import type { MeasureListItem } from "@/shared/api"

import { rankByQuery } from "@/shared/lib"
import { MeasureList } from "./MeasureList"

type Props = {
  title: string | null
  items: MeasureListItem[]
  onClose: () => void
}

export function MeasureListModal({ title, items, onClose }: Props) {
  const [query, setQuery] = useState("")
  const shown = rankByQuery(items, query, m => `${m.code} ${m.title} ${m.responsibleUnit ?? ""} ${m.risk?.code ?? ""}`)
  const close = () => {
    setQuery("")
    onClose()
  }

  return (
    <Modal
      opened={title !== null}
      onClose={close}
      title={
        <Group gap='xs'>
          <Text fw={700}>{title}</Text>
          <Text
            c='dimmed'
            size='sm'
          >
            {query ? `${shown.length} з ${items.length}` : items.length}
          </Text>
        </Group>
      }
      size='xl'
      scrollAreaComponent={ScrollArea.Autosize}
    >
      {items.length > 5 && (
        <TextInput
          placeholder='Пошук: номер, назва, підрозділ, ризик'
          leftSection={<IconSearch size={16} />}
          value={query}
          onChange={e => setQuery(e.currentTarget.value)}
          mb='md'
          data-autofocus
        />
      )}
      <MeasureList
        items={shown}
        empty={query ? "Нічого не знайдено" : "Заходів немає"}
      />
    </Modal>
  )
}
