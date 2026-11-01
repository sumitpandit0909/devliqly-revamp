import { useSyncExternalStore } from 'react'

// Minimal History API router: the site only needs a handful of flat routes
const listeners = new Set()

function subscribe(fn) {
  listeners.add(fn)
  window.addEventListener('popstate', fn)
  return () => {
    listeners.delete(fn)
    window.removeEventListener('popstate', fn)
  }
}

export const usePath = () => useSyncExternalStore(subscribe, () => window.location.pathname)

export function navigate(to) {
  const url = new URL(to, window.location.origin)
  if (url.pathname + url.hash === window.location.pathname + window.location.hash) return
  window.history.pushState({}, '', url.pathname + url.hash)
  listeners.forEach((fn) => fn())
}
