import { useSyncExternalStore } from "react"

import type { Role, User } from "./types"

const USER_KEY = "mitra.user"
const LEGACY_KEYS = ["acm.token", "acm.user"]

type Session = { user: User | null; manualLogout: boolean }

const storage = () => {
  try {
    return sessionStorage
  } catch {
    return null
  }
}

const read = (): User | null => {
  try {
    const raw = storage()?.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

const write = (user: User | null) => {
  try {
    if (user === null) storage()?.removeItem(USER_KEY)
    else storage()?.setItem(USER_KEY, JSON.stringify(user))
  } catch {
    return
  }
}

try {
  LEGACY_KEYS.forEach(k => localStorage.removeItem(k))
} catch {
  /* storage blocked */
}

let state: Session = { user: read(), manualLogout: false }
const listeners = new Set<() => void>()

const emit = () => listeners.forEach(l => l())

export const session = {
  get: () => state,
  signedIn: () => state.user !== null,
  role: (): Role | null => state.user?.role ?? null,
  set(user: User) {
    state = { user, manualLogout: false }
    write(user)
    emit()
  },
  setUser(user: User) {
    if (!state.user) return
    state = { ...state, user }
    write(user)
    emit()
  },
  clear(manual = false) {
    state = { user: null, manualLogout: manual }
    write(null)
    emit()
  },
  subscribe(listener: () => void) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
}

export const useSession = () => useSyncExternalStore(session.subscribe, session.get, session.get)
