import { useEffect, useRef, useState } from "react"
import { Skeleton } from "@mantine/core"
import type { ReactNode } from "react"

type DeferredProps = {
  height?: number
  rootMargin?: string
  children: ReactNode
}

type Job = { run: () => boolean }
const queue: Job[] = []
let busy = false

const pump = () => {
  busy = false
  while (queue.length) {
    const job = queue.shift()!
    if (job.run()) {
      busy = true
      return
    }
  }
}

const enqueue = (job: Job) => {
  queue.push(job)
  if (!busy) {
    busy = true
    setTimeout(pump, 0)
  }
}

export function Deferred({ height = 280, rootMargin = "0px", children }: DeferredProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(typeof IntersectionObserver === "undefined")
  const queued = useRef(false)

  useEffect(() => {
    if (shown) return
    const el = ref.current
    if (!el) return
    let alive = true
    const job: Job = {
      run: () => {
        if (!alive) return false
        queued.current = true
        setShown(true)
        return true
      },
    }
    const io = new IntersectionObserver(
      entries => {
        if (entries.some(e => e.isIntersecting)) {
          io.disconnect()
          enqueue(job)
        }
      },
      { rootMargin }
    )
    io.observe(el)
    return () => {
      alive = false
      io.disconnect()
    }
  }, [shown, rootMargin])

  useEffect(() => {
    if (shown && queued.current) {
      queued.current = false
      setTimeout(pump, 0)
    }
  }, [shown])

  useEffect(
    () => () => {
      if (queued.current) {
        queued.current = false
        setTimeout(pump, 0)
      }
    },
    []
  )

  if (shown) return children
  return (
    <div
      ref={ref}
      aria-hidden
    >
      <Skeleton
        h={height}
        radius='md'
        animate={false}
      />
    </div>
  )
}
