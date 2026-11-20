import type { PopoverProps } from "@mantine/core"

export const headerDropdown = {
  position: "bottom-end",
  shadow: "md",
  floatingStrategy: "fixed",
  preventPositionChangeWhenVisible: true,
  middlewares: { flip: false, shift: { padding: 8 }, inline: false },
  transitionProps: { transition: "fade", duration: 120 },
} satisfies Partial<PopoverProps>

export const dropdownWidth = (px: number) => `min(${px}px, calc(100vw - 16px))`
