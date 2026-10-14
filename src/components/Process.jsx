import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { PROCESS } from '../data'

export default function Process() {
  const root = useRef(null)

  useGSAP(() => {
    if (prefersReducedMotion()) return
    gsap.to('.process__rail i', {
      scaleY: 1, ease: 'none',
      scrollTrigger: { trigger: '.process__list', start: 'top 60%', end: 'bottom 60%', scrub: true },
    })
    gsap.utils.toArray('.step').forEach((step) => {
      const tl = gsap.timeline({ scrollTrigger: { trigger: step, start: 'top 70%', toggleActions: 'play none none reverse' } })
      tl.from(step.querySelector('.step__no'), { xPercent: -30, autoAlpha: 0, duration: 1, ease: 'power4.out' })
        .from(step.querySelectorAll('h3, p'), { y: 30, autoAlpha: 0, stagger: 0.1, duration: 0.8, ease: 'power3.out' }, '-=0.7')
        .add(() => step.classList.toggle('is-active'), 0.1)
      // Big outlined numbers move at a different speed to the copy
      gsap.fromTo(step.querySelector('.step__no'), { yPercent: 30 }, {
        yPercent: -30, ease: 'none', scrollTrigger: { trigger: step, start: 'top bottom', end: 'bottom top', scrub: true },
      })
    })
  }, { scope: root })

  return (
    <section className="process section" id="process" ref={root}>
      <div className="container">
        <div className="section-head">
          <p className="label">( Process )</p>
          <h2 className="h2">From idea to a <em>live agent</em> in weeks</h2>
        </div>
        <div className="process__list">
          <span className="process__rail" aria-hidden="true"><i /></span>
          {PROCESS.map((p) => (
            <div className="step" key={p.no}>
              <span className="step__dot" aria-hidden="true" />
              <span className="step__no" aria-hidden="true">{p.no}</span>
              <div className="step__body">
                <h3>{p.title}</h3>
                <p>{p.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
