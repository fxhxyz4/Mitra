import { ActionIcon, Group, Menu, SegmentedControl, useMantineColorScheme } from "@mantine/core"
import { IconCheck, IconDeviceDesktop, IconMoon, IconPalette, IconSun } from "@tabler/icons-react"
import type { ThemePresetId } from "@/app/theme"
import type { MantineColorScheme } from "@mantine/core"

import { presets, useThemePreset } from "@/app/theme"
import classes from "./AppearanceMenu.module.scss"
import { dropdownWidth, headerDropdown } from "./dropdown"

const schemes: { value: MantineColorScheme; label: string; title: string; icon: typeof IconSun }[] = [
  { value: "light", label: "Світла", title: "Світлий режим", icon: IconSun },
  { value: "dark", label: "Темна", title: "Темний режим", icon: IconMoon },
  { value: "auto", label: "Авто", title: "Як у системі", icon: IconDeviceDesktop },
]

function Swatches({ colors }: { colors: string[] }) {
  return (
    <span className={classes.swatches}>
      {colors.map(color => (
        <span
          key={color}
          className={classes.swatch}
          style={{ background: color }}
        />
      ))}
    </span>
  )
}

export function AppearanceMenu() {
  const { preset, setPreset } = useThemePreset()
  const { colorScheme, setColorScheme } = useMantineColorScheme()

  return (
    <Menu
      {...headerDropdown}
      width={dropdownWidth(248)}
      closeOnItemClick={false}
    >
      <Menu.Target>
        <ActionIcon
          variant='default'
          size='lg'
          aria-label='Оформлення'
          title='Оформлення'
        >
          <IconPalette size={18} />
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>Режим</Menu.Label>
        <div className={classes.scheme}>
          <SegmentedControl
            fullWidth
            size='xs'
            value={colorScheme}
            onChange={v => setColorScheme(v as MantineColorScheme)}
            aria-label='Режим оформлення'
            data={schemes.map(({ value, label, title, icon: Icon }) => ({
              value,
              label: (
                <Group
                  gap={4}
                  justify='center'
                  wrap='nowrap'
                  title={title}
                >
                  <Icon size={14} />
                  {label}
                </Group>
              ),
            }))}
          />
        </div>
        <Menu.Divider />
        <Menu.Label>Тема оформлення</Menu.Label>
        {Object.values(presets).map(p => (
          <Menu.Item
            key={p.id}
            onClick={() => setPreset(p.id as ThemePresetId)}
            leftSection={<Swatches colors={p.swatches} />}
            rightSection={p.id === preset ? <IconCheck size={16} /> : null}
            aria-checked={p.id === preset}
          >
            {p.label}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  )
}
