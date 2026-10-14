import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { INTEGRATIONS } from '../data'
import Logo from './Logo'

const INNER = INTEGRATIONS.slice(0, 6)
const OUTER = INTEGRATIONS.slice(6)

export default function Integrations() {
  const root = useRef(null)

  useGSAP(() => {
    if (prefersReducedMotion()) return
    const st = { trigger: root.current, start: 'top bottom', end: 'bottom top', scrub: 1 }
    // Rings spin in opposite directions with scroll; pills counter-rotate to stay upright
    gsap.to('.ring--inner', { rotate: 120, ease: 'none', scrollTrigger: st })
    gsap.to('.ring--inner .pill', { rotate: -120, ease: 'none', scrollTrigger: st })
    gsap.to('.ring--outer', { rotate: -90, ease: 'none', scrollTrigger: st })
    gsap.to('.ring--outer .pill', { rotate: 90, ease: 'none', scrollTrigger: st })
    gsap.from('.orbit', { scale: 0.7, autoAlpha: 0, duration: 1.4, ease: 'expo.out', scrollTrigger: { trigger: root.current, start: 'top 65%' } })
    gsap.from('.integrations__copy > *', { y: 40, autoAlpha: 0, stagger: 0.1, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: root.current, start: 'top 70%' } })
  }, { scope: root })

  const ring = (items, cls) => (
    <div className={`ring ${cls}`}>
      {items.map((name, i) => (
        <span className="ring__slot" key={name} style={{ '--a': `${(360 / items.length) * i}deg` }}>
          <span className="pill">{name}</span>
        </span>
      ))}
    </div>
  )

  return (
    <section className="integrations section" ref={root}>
      <div className="container integrations__grid">
        <div className="integrations__copy">
          <p className="label">( Integrations )</p>
          <h2 className="h2">Plugs into the stack <em>you already use</em></h2>
          <p className="lead">
            CRMs, helpdesks, telephony, payments, calendars and messaging. Your agents read and write
            data where your team already works, so nothing has to be migrated.
          </p>
        </div>
        <div className="orbit" aria-label={`Integrations: ${INTEGRATIONS.join(', ')}`}>
          {ring(OUTER, 'ring--outer')}
          {ring(INNER, 'ring--inner')}
          <div className="orbit__core"><Logo /></div>
        </div>
      </div>
    </section>
  )
}
