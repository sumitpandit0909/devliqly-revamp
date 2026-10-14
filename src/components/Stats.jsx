import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { STATS } from '../data'

export default function Stats() {
  const root = useRef(null)

  useGSAP(() => {
    if (prefersReducedMotion()) return
    gsap.utils.toArray('.stat__num b').forEach((el) => {
      const end = Number(el.dataset.value)
      const o = { v: 0 }
      el.textContent = '0'
      gsap.to(o, {
        v: end, duration: 2, ease: 'power3.out',
        onUpdate: () => { el.textContent = Math.round(o.v) },
        scrollTrigger: { trigger: root.current, start: 'top 75%' },
      })
    })
    gsap.from('.stat', { y: 60, autoAlpha: 0, stagger: 0.12, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: root.current, start: 'top 75%' } })
  }, { scope: root })

  return (
    <section className="stats" ref={root}>
      <div className="container stats__grid">
        {STATS.map((s) => (
          <div className="stat" key={s.label}>
            <div className="stat__num"><b data-value={s.value}>{s.value}</b><span>{s.suffix}</span></div>
            <p>{s.label}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
