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
  // Targets marked data-scroll-focus leave room for the nav and focus their first field on arrival
  const focusable = target !== 0 && target.hasAttribute('data-scroll-focus')
  const focus = (tries = 0) => {
    // Skip on touch devices so the on-screen keyboard doesn't pop up uninvited
    if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
    // The target may still be fading in (visibility: hidden can't take focus), so retry briefly
    if (getComputedStyle(target).visibility === 'hidden' && tries < 15) {
      setTimeout(() => focus(tries + 1), 100)
      return
    }
    target.querySelector('input:not([tabindex="-1"]), textarea, select')?.focus({ preventScroll: true })
  }
  if (lenisRef.current) {
    lenisRef.current.scrollTo(target, { offset: focusable ? -100 : 0, duration: 1.4, onComplete: focusable ? () => focus() : undefined })
  } else if (target === 0) {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } else {
    target.scrollIntoView({ behavior: 'smooth', block: focusable ? 'center' : 'start' })
    if (focusable) setTimeout(() => focus(), 700)
  }
}

export { gsap, ScrollTrigger, useGSAP }
