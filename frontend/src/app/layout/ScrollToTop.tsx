import { useLayoutEffect, useRef } from "react"
import { useLocation, useNavigationType } from "react-router"

export function ScrollToTop() {
  const { pathname } = useLocation()
  const type = useNavigationType()
  const last = useRef(pathname)

  useLayoutEffect(() => {
    if (last.current === pathname) return
    last.current = pathname
    if (type !== "POP") window.scrollTo(0, 0)
  }, [pathname, type])

  return null
}
