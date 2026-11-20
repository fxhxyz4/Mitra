import { queryOptions, useQuery } from "@tanstack/react-query"

import { http } from "./http"
import type { Dictionaries, Indicator, OrgUnit, Program, Risk } from "./types"

const long = 5 * 60_000

export const reference = {
  all: ["reference"] as const,
  dictionaries: () =>
    queryOptions({
      queryKey: [...reference.all, "dictionaries"],
      queryFn: () => http<Dictionaries>("/admin/dictionaries"),
      staleTime: long,
    }),
  orgUnits: () =>
    queryOptions({
      queryKey: [...reference.all, "org-units"],
      queryFn: () => http<OrgUnit[]>("/admin/org-units"),
      staleTime: long,
    }),
  risks: () => queryOptions({ queryKey: [...reference.all, "risks"], queryFn: () => http<Risk[]>("/risks") }),
  indicators: () =>
    queryOptions({ queryKey: [...reference.all, "indicators"], queryFn: () => http<Indicator[]>("/indicators") }),
  programs: () =>
    queryOptions({ queryKey: [...reference.all, "programs"], queryFn: () => http<Program[]>("/programs") }),
}

export const useDictionaries = () => useQuery(reference.dictionaries())
export const useOrgUnits = () => useQuery(reference.orgUnits())
export const useRisks = () => useQuery(reference.risks())
export const useIndicators = () => useQuery(reference.indicators())
export const usePrograms = () => useQuery(reference.programs())
