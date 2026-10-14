import { useRef, useState } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { FAQS } from '../data'

export default function Faq() {
  const root = useRef(null)
  const [open, setOpen] = useState(0)

  useGSAP(() => {
    if (prefersReducedMotion()) return
    gsap.from('.faq__item', { y: 40, autoAlpha: 0, stagger: 0.08, duration: 0.9, ease: 'power3.out', scrollTrigger: { trigger: '.faq__list', start: 'top 80%' } })
  }, { scope: root })

  return (
    <section className="faq section" id="faq" ref={root}>
      <div className="container faq__grid">
        <div className="faq__side">
          <p className="label">( FAQ )</p>
          <h2 className="h2">Questions, <em>answered</em></h2>
        </div>
        <div className="faq__list">
          {FAQS.map((f, i) => (
            <div className={`faq__item ${open === i ? 'is-open' : ''}`} key={f.q}>
              <button className="faq__q" aria-expanded={open === i} onClick={() => setOpen(open === i ? -1 : i)}>
                <span>{f.q}</span>
                <i aria-hidden="true" />
              </button>
              <div className="faq__a"><div><p>{f.a}</p></div></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
