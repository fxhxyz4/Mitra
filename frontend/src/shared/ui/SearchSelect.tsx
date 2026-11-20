import { useEffect, useEffectEvent, useState } from "react"
import { CloseButton, Combobox, InputBase, Pill, PillsInput, useCombobox } from "@mantine/core"
import type { BoxProps, MantineSize } from "@mantine/core"
import type { ReactNode } from "react"

import { rankByQuery, SEARCH } from "@/shared/lib"

export type SearchOption = { value: string; label: string }

type BaseProps = {
  data: SearchOption[]
  label?: ReactNode
  description?: ReactNode
  placeholder?: string
  error?: ReactNode
  required?: boolean
  disabled?: boolean
  clearable?: boolean
  size?: MantineSize
  w?: BoxProps["w"]
  style?: BoxProps["style"]
  nothingFoundMessage?: ReactNode
  "aria-label"?: string
}

function useRankedSearch(data: SearchOption[]) {
  const [search, setSearch] = useState("")
  const typed = search.trim() !== ""
  const options = rankByQuery(data, search, o => o.label).slice(0, SEARCH.limit)
  const combobox = useCombobox({ onDropdownClose: () => combobox.resetSelectedOption() })
  const highlightBest = useEffectEvent(() => combobox.selectFirstOption())

  useEffect(() => {
    if (typed) highlightBest()
  }, [search, typed])

  return { search, setSearch, options, combobox }
}

function OptionList({ options, active, empty }: { options: SearchOption[]; active?: string[]; empty: ReactNode }) {
  return (
    <Combobox.Options
      mah={260}
      style={{ overflowY: "auto" }}
    >
      {options.length ? (
        options.map(o => (
          <Combobox.Option
            key={o.value}
            value={o.value}
            active={active?.includes(o.value)}
          >
            {o.label}
          </Combobox.Option>
        ))
      ) : (
        <Combobox.Empty>{empty}</Combobox.Empty>
      )}
    </Combobox.Options>
  )
}

export function SearchSelect({
  data,
  value,
  onChange,
  allowDeselect = true,
  clearable,
  placeholder,
  nothingFoundMessage = SEARCH.nothingFound,
  ...input
}: BaseProps & { value: string | null; onChange: (value: string | null) => void; allowDeselect?: boolean }) {
  const { search, setSearch, options, combobox } = useRankedSearch(data)
  const selected = data.find(o => o.value === value)

  const pick = (next: string | null) => {
    onChange(next)
    setSearch("")
  }

  return (
    <Combobox
      store={combobox}
      onOptionSubmit={v => {
        pick(v === value && allowDeselect ? null : v)
        combobox.closeDropdown()
      }}
    >
      <Combobox.Target>
        <InputBase
          {...input}
          value={search || selected?.label || ""}
          onChange={e => {
            setSearch(e.currentTarget.value)
            combobox.openDropdown()
          }}
          onClick={() => combobox.openDropdown()}
          onFocus={() => combobox.openDropdown()}
          onBlur={() => {
            setSearch("")
            combobox.closeDropdown()
          }}
          onKeyDown={e => e.key === "Escape" && setSearch("")}
          placeholder={selected ? undefined : placeholder}
          rightSection={
            clearable && value && !input.disabled ? (
              <CloseButton
                size='sm'
                aria-label='Очистити'
                onMouseDown={e => e.preventDefault()}
                onClick={() => pick(null)}
              />
            ) : (
              <Combobox.Chevron />
            )
          }
          rightSectionPointerEvents={clearable && value ? "all" : "none"}
          autoComplete='off'
        />
      </Combobox.Target>
      <Combobox.Dropdown>
        <OptionList
          options={options}
          active={value ? [value] : []}
          empty={nothingFoundMessage}
        />
      </Combobox.Dropdown>
    </Combobox>
  )
}

export function SearchMultiSelect({
  data,
  value,
  onChange,
  clearable,
  placeholder,
  nothingFoundMessage = SEARCH.nothingFound,
  label,
  description,
  error,
  required,
  disabled,
  size,
  w,
  style,
  "aria-label": ariaLabel,
}: BaseProps & { value: string[]; onChange: (value: string[]) => void }) {
  const free = data.filter(o => !value.includes(o.value))
  const { search, setSearch, options, combobox } = useRankedSearch(free)
  const labelOf = new Map(data.map(o => [o.value, o.label]))

  return (
    <Combobox
      store={combobox}
      onOptionSubmit={v => {
        onChange([...value, v])
        setSearch("")
      }}
    >
      <Combobox.DropdownTarget>
        <PillsInput
          label={label}
          description={description}
          error={error}
          required={required}
          disabled={disabled}
          size={size}
          w={w}
          style={style}
          onClick={() => {
            combobox.focusTarget()
            combobox.openDropdown()
          }}
          rightSection={
            clearable && value.length && !disabled ? (
              <CloseButton
                size='sm'
                aria-label='Очистити'
                onMouseDown={e => e.preventDefault()}
                onClick={() => onChange([])}
              />
            ) : (
              <Combobox.Chevron />
            )
          }
          rightSectionPointerEvents={clearable && value.length ? "all" : "none"}
        >
          <Pill.Group>
            {value.map(v => (
              <Pill
                key={v}
                withRemoveButton={!disabled}
                onRemove={() => onChange(value.filter(x => x !== v))}
              >
                {labelOf.get(v) ?? v}
              </Pill>
            ))}
            <Combobox.EventsTarget>
              <PillsInput.Field
                value={search}
                onChange={e => {
                  setSearch(e.currentTarget.value)
                  combobox.openDropdown()
                }}
                onFocus={() => combobox.openDropdown()}
                onBlur={() => {
                  setSearch("")
                  combobox.closeDropdown()
                }}
                onKeyDown={e => {
                  if (e.key === "Backspace" && !search && value.length) onChange(value.slice(0, -1))
                  if (e.key === "Escape") setSearch("")
                }}
                placeholder={value.length ? undefined : placeholder}
                aria-label={ariaLabel ?? (typeof label === "string" ? label : undefined)}
                disabled={disabled}
                autoComplete='off'
              />
            </Combobox.EventsTarget>
          </Pill.Group>
        </PillsInput>
      </Combobox.DropdownTarget>
      <Combobox.Dropdown>
        <OptionList
          options={options}
          empty={nothingFoundMessage}
        />
      </Combobox.Dropdown>
    </Combobox>
  )
}
