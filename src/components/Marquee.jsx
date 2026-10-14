import { useRef } from 'react'
import { gsap, ScrollTrigger, useGSAP, prefersReducedMotion } from '../lib/motion'

const WORDS = ['Chatbots', 'Support Agents', 'Call Agents', 'Voice AI', 'Agent Workflows']

// Infinite marquee whose speed and direction respond to scroll velocity
export default function Marquee() {
  const root = useRef(null)

  useGSAP(() => {
    if (prefersReducedMotion()) return
    const rows = gsap.utils.toArray('.marquee__track').map((track, i) => {
      const dir = i % 2 ? 1 : -1
      return gsap.fromTo(track, { xPercent: dir === -1 ? 0 : -50 }, { xPercent: dir === -1 ? -50 : 0, duration: 28, ease: 'none', repeat: -1 })
    })
    const skew = gsap.quickTo('.marquee__track', 'skewX', { duration: 0.4, ease: 'power3' })
    ScrollTrigger.create({
      trigger: root.current,
      start: 'top bottom',
      end: 'bottom top',
      onUpdate: (self) => {
        const v = self.getVelocity()
        const boost = Math.min(1 + Math.abs(v) / 300, 6)
        rows.forEach((t) => {
          gsap.killTweensOf(t, 'timeScale')
          gsap.timeline().to(t, { timeScale: boost, duration: 0.2 }).to(t, { timeScale: 1, duration: 1.2, ease: 'power2.out' })
        })
        skew(gsap.utils.clamp(-12, 12, v / -250))
        gsap.delayedCall(0.15, () => skew(0))
      },
    })
    gsap.to(root.current, { rotate: -2.5, ease: 'none', scrollTrigger: { trigger: root.current, scrub: true, start: 'top bottom', end: 'bottom top' } })
  }, { scope: root })

  const row = (key) => (
    <div className="marquee__track" key={key}>
      {[0, 1].map((dup) => (
        <div className="marquee__group" key={dup} aria-hidden={dup === 1}>
          {WORDS.map((w, i) => (
            <span key={i} className={i % 2 ? 'outline' : ''}>
              {w}<i className="marquee__star">✺</i>
            </span>
          ))}
        </div>
      ))}
    </div>
  )

  return (
    <section className="marquee" ref={root} aria-label="What we build">
      {row('a')}
      {row('b')}
    </section>
  )
}
