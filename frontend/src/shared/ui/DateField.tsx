import { DatePickerInput } from "@mantine/dates"
import { IconCalendar } from "@tabler/icons-react"
import type { BoxProps, MantineSize } from "@mantine/core"
import type { ReactNode } from "react"

type DateFieldProps = {
  value: string | null
  onChange: (value: string | null) => void
  label?: ReactNode
  description?: ReactNode
  placeholder?: string
  error?: ReactNode
  required?: boolean
  clearable?: boolean
  disabled?: boolean
  minDate?: string
  maxDate?: string
  size?: MantineSize
  w?: BoxProps["w"]
  style?: BoxProps["style"]
  leftSection?: ReactNode
  "aria-label"?: string
}

export function DateField({ value, onChange, placeholder = "Оберіть дату", leftSection, ...props }: DateFieldProps) {
  return (
    <DatePickerInput
      {...props}
      value={value || null}
      onChange={v => onChange(v ? String(v).slice(0, 10) : null)}
      valueFormat='DD.MM.YYYY'
      placeholder={placeholder}
      leftSection={leftSection ?? <IconCalendar size={16} />}
      leftSectionPointerEvents='none'
      popoverProps={{ shadow: "md", withinPortal: true }}
    />
  )
}
