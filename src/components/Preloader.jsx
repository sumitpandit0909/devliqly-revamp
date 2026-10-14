import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'

export default function Preloader({ onDone }) {
  const root = useRef(null)
  const count = useRef(null)

  useGSAP(() => {
    if (prefersReducedMotion()) {
      gsap.set(root.current, { display: 'none' })
      onDone()
      return
    }
    const counter = { v: 0 }
    const tl = gsap.timeline({ onComplete: onDone })
    tl.from('.pre__word span', { yPercent: 110, stagger: 0.04, duration: 0.8, ease: 'power4.out' })
      .to(counter, {
        v: 100,
        duration: 1.6,
        ease: 'power2.inOut',
        onUpdate: () => { count.current.textContent = String(Math.round(counter.v)).padStart(3, '0') },
      }, 0)
      .to('.pre__bar i', { scaleX: 1, duration: 1.6, ease: 'power2.inOut' }, 0)
      .to('.pre__word span', { yPercent: -110, stagger: 0.03, duration: 0.6, ease: 'power3.in' }, '+=0.1')
      .to(root.current, { clipPath: 'inset(0 0 100% 0)', duration: 1, ease: 'expo.inOut' }, '-=0.25')
      .set(root.current, { display: 'none' })
  }, { scope: root })

  return (
    <div className="pre" ref={root} aria-hidden="true">
      <div className="pre__word">
        {'DEVLIQLY'.split('').map((c, i) => <span key={i}>{c}</span>)}
      </div>
      <div className="pre__meta">
        <span>AI agents · loading</span>
        <span ref={count} className="pre__count">000</span>
      </div>
      <div className="pre__bar"><i /></div>
    </div>
  )
}
