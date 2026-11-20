import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { LoginResult, Reminder, User, UserWithToken } from "@/shared/api"

import { http, post, session, useSession } from "@/shared/api"

export function useLogin() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (token: string) => {
      const res = await post<LoginResult>("/auth/login", { token: token.trim() })
      const user: User = { id: res.id, displayName: res.displayName, role: res.role, orgUnitId: res.orgUnitId }
      return user
    },
    onSuccess: user => {
      client.clear()
      session.set(user)
    },
  })
}

export function useDemoAccounts(enabled = true) {
  return useQuery({
    queryKey: ["auth", "demo-accounts"],
    queryFn: () => http<UserWithToken[]>("/auth/demo-accounts"),
    enabled,
    staleTime: Infinity,
  })
}

export function useLogout() {
  const client = useQueryClient()
  return () => {
    session.clear(true)
    client.clear()
    void post("/auth/logout").catch(() => undefined)
  }
}

export function useMe() {
  const { user } = useSession()
  const signedInAs = user?.id ?? null
  return useQuery({
    queryKey: [
      "auth",
      "me",
      signedInAs,
    ],
    queryFn: async () => {
      const user = await http<User>("/auth/me")
      session.setUser(user)
      return user
    },
    enabled: Boolean(signedInAs),
    staleTime: 5 * 60_000,
  })
}

export function useReminders() {
  const { user } = useSession()
  return useQuery({
    queryKey: ["reminders", user?.id ?? null],
    queryFn: () => http<Reminder[]>("/reminders"),
    enabled: Boolean(user),
    refetchInterval: 60_000,
  })
}
