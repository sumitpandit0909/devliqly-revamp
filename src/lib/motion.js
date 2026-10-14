import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(ScrollTrigger, useGSAP)

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

// Lenis instance shared across components (set by App)
export const lenisRef = { current: null }

export function scrollToHash(hash) {
  const target = hash === '#top' ? 0 : document.querySelector(hash)
  if (target === null) return
  if (lenisRef.current) lenisRef.current.scrollTo(target, { offset: 0, duration: 1.4 })
  else if (target === 0) window.scrollTo({ top: 0, behavior: 'smooth' })
  else target.scrollIntoView({ behavior: 'smooth' })
}

export { gsap, ScrollTrigger, useGSAP }
