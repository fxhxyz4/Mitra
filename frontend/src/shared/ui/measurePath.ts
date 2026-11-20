import { session } from "@/shared/api"
import { paths, withId } from "@/shared/config"

export const measurePath = (id: string) => withId(session.role() === "EXECUTOR" ? paths.myMeasure : paths.measure, id)
