import { DatesProvider } from "@mantine/dates"
import { Notifications } from "@mantine/notifications"
import { QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"

import "dayjs/locale/uk"

import { ThemePresetProvider } from "@/app/theme"
import { queryClient } from "@/shared/api"

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemePresetProvider>
        <DatesProvider settings={{ locale: "uk", firstDayOfWeek: 1 }}>
          <Notifications position='top-right' />
          {children}
        </DatesProvider>
      </ThemePresetProvider>
    </QueryClientProvider>
  )
}
