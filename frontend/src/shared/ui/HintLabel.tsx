import { Text, Tooltip } from "@mantine/core"
import type { ReactNode } from "react"

type HintLabelProps = {
  children: ReactNode
  hint: ReactNode
  formula?: string
  width?: number
}

export function HintLabel({ children, hint, formula, width = 260 }: HintLabelProps) {
  return (
    <Tooltip
      multiline
      w={width}
      withArrow
      arrowSize={7}
      openDelay={120}
      position='top'
      events={{ hover: true, focus: true, touch: true }}
      classNames={{ tooltip: "app-hint", arrow: "app-hint-arrow" }}
      label={
        <>
          {formula && <div className='app-hint-formula'>{formula}</div>}
          <div>{hint}</div>
        </>
      }
    >
      <Text
        span
        inherit
        className='app-hint-target'
        tabIndex={0}
      >
        {children}
      </Text>
    </Tooltip>
  )
}
