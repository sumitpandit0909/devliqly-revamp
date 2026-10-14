import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'

const TEXT = 'Your customers call at 2 AM, message on WhatsApp during lunch and expect an answer in seconds. We build AI agents that never sleep, never put anyone on hold, and plug straight into the tools your team already uses.'
const HIGHLIGHT = new Set(['2', 'AM,', 'WhatsApp', 'seconds.', 'never'])

export default function Statement() {
  const root = useRef(null)

  useGSAP(() => {
    if (prefersReducedMotion()) return
    gsap.fromTo('.statement__text .w',
      { opacity: 0.12 },
      { opacity: 1, stagger: 0.05, ease: 'none', scrollTrigger: { trigger: '.statement__text', start: 'top 80%', end: 'bottom 45%', scrub: true } })
    gsap.from('.statement__label', { x: -40, autoAlpha: 0, duration: 1, scrollTrigger: { trigger: root.current, start: 'top 75%' } })
    gsap.to('.statement__blob', { yPercent: -60, rotate: 90, ease: 'none', scrollTrigger: { trigger: root.current, start: 'top bottom', end: 'bottom top', scrub: true } })
  }, { scope: root })

  return (
    <section className="statement section" ref={root}>
      <div className="statement__blob" aria-hidden="true" />
      <div className="container">
        <p className="statement__label label">( About Devliqly )</p>
        <p className="statement__text">
          {TEXT.split(' ').map((w, i) => (
            <span key={i} className={`w ${HIGHLIGHT.has(w) ? 'hl' : ''}`}>{w} </span>
          ))}
        </p>
      </div>
    </section>
  )
}
