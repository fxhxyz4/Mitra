import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AiSettings, OrgUnit, Role, User, UserWithToken } from "@/shared/api"

import { aiStatusQuery, http, patch, post, put, reference } from "@/shared/api"

export const useUsers = () => useQuery({ queryKey: ["admin", "users"], queryFn: () => http<User[]>("/admin/users") })

export function useCreateUser() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (data: { displayName: string; role: Role; orgUnitId: string; adminPassword?: string }) =>
      post<UserWithToken>("/admin/users", data),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin", "users"] }),
  })
}

export function useUpdateUser() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string
      role?: Role
      orgUnitId?: string
      displayName?: string
      adminPassword?: string
    }) => patch<User>(`/admin/users/${id}`, data),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin", "users"] }),
  })
}

export function useDeleteUser() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, adminPassword }: { id: string; adminPassword?: string }) =>
      http<void>(`/admin/users/${id}`, {
        method: "DELETE",
        headers: adminPassword ? { "X-Admin-Password": adminPassword } : undefined,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin", "users"] }),
  })
}

export const useReissueToken = () =>
  useMutation({
    mutationFn: ({ id, adminPassword }: { id: string; adminPassword?: string }) =>
      http<UserWithToken>(`/admin/users/${id}/token`, {
        method: "POST",
        headers: adminPassword ? { "X-Admin-Password": adminPassword } : undefined,
      }),
  })

export function useCreateOrgUnit() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; parentId?: string | null }) => post<OrgUnit>("/admin/org-units", data),
    onSuccess: () => client.invalidateQueries({ queryKey: reference.orgUnits().queryKey }),
  })
}

const aiSettingsKey = [
  "admin",
  "settings",
  "ai",
] as const

export const useAiSettings = () =>
  useQuery({ queryKey: aiSettingsKey, queryFn: () => http<AiSettings>("/admin/settings/ai") })

export function useSetAiSettings() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (enabled: boolean) => put<AiSettings>("/admin/settings/ai", { enabled }),
    onSuccess: data => {
      client.setQueryData(aiSettingsKey, data)
      client.invalidateQueries({ queryKey: aiStatusQuery.queryKey })
    },
  })
}
