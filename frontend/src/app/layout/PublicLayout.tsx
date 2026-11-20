import { Outlet } from "react-router"

import { AppearanceMenu } from "./AppearanceMenu"
import classes from "./PublicLayout.module.scss"
import { ScrollToTop } from "./ScrollToTop"

export function PublicLayout() {
  return (
    <>
      <div className={classes.controls}>
        <AppearanceMenu />
      </div>
      <main>
        <Outlet />
        <ScrollToTop />
      </main>
    </>
  )
}
