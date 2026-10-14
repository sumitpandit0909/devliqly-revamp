import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { TESTIMONIALS } from '../data'

export default function Testimonials() {
  const root = useRef(null)

  useGSAP(() => {
    if (prefersReducedMotion()) return
    // Two rows slide in opposite directions as the section passes through the viewport
    const st = { trigger: root.current, start: 'top bottom', end: 'bottom top', scrub: 1 }
    gsap.fromTo('.tst__row--a', { xPercent: 0 }, { xPercent: -25, ease: 'none', scrollTrigger: st })
    gsap.fromTo('.tst__row--b', { xPercent: -25 }, { xPercent: 0, ease: 'none', scrollTrigger: st })
    gsap.from('.tst__head > *', { y: 40, autoAlpha: 0, stagger: 0.1, duration: 1, scrollTrigger: { trigger: root.current, start: 'top 70%' } })
  }, { scope: root })

  const card = (t, k) => (
    <figure className="tst" key={k}>
      <span className="tst__q" aria-hidden="true">“</span>
      <blockquote>{t.quote}</blockquote>
      <figcaption>
        <span className="tst__avatar">{t.name.split(' ').map((n) => n[0]).join('')}</span>
        <span><b>{t.name}</b><small>{t.role}</small></span>
      </figcaption>
    </figure>
  )

  return (
    <section className="testimonials section" id="clients" ref={root}>
      <div className="container tst__head">
        <p className="label">( Testimonials )</p>
        <h2 className="h2">What our <em>clients</em> say</h2>
      </div>
      <div className="tst__rows">
        <div className="tst__row tst__row--a">{[...TESTIMONIALS, ...TESTIMONIALS.slice(0, 2)].map((t, i) => card(t, 'a' + i))}</div>
        <div className="tst__row tst__row--b" aria-hidden="true">{[...TESTIMONIALS.slice(2), ...TESTIMONIALS].map((t, i) => card(t, 'b' + i))}</div>
      </div>
    </section>
  )
}
