import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { CONTACT } from '../data'
import Magnetic from './Magnetic'

export default function Cta() {
  const root = useRef(null)

  useGSAP(() => {
    if (prefersReducedMotion()) return
    const tl = gsap.timeline({ scrollTrigger: { trigger: root.current, start: 'top 85%', end: 'center center', scrub: 1 } })
    tl.from('.cta__line--1', { xPercent: -30, ease: 'none' }, 0)
      .from('.cta__line--2', { xPercent: 30, ease: 'none' }, 0)
      .from('.cta__line--3', { xPercent: -20, ease: 'none' }, 0)
      .from('.cta__circle', { scale: 0.2, rotate: -180, ease: 'none' }, 0)
    gsap.to('.cta__bg', { scale: 1.4, ease: 'none', scrollTrigger: { trigger: root.current, start: 'top bottom', end: 'bottom top', scrub: true } })
  }, { scope: root })

  return (
    <section className="cta" id="contact" ref={root}>
      <div className="cta__bg" aria-hidden="true" />
      <div className="container">
        <p className="label">( Get in touch )</p>
        <h2 className="cta__title">
          <span className="cta__line cta__line--1">Ready to hire</span>
          <span className="cta__line cta__line--2">your first</span>
          <span className="cta__line cta__line--3"><em>AI agent?</em></span>
        </h2>
        <div className="cta__row">
          <p className="lead">
            Tell us what your customers ask most often. Within 48 hours we&apos;ll come back with a
            free agent blueprint and a demo call.
          </p>
          <Magnetic strength={0.5}>
            <a className="cta__circle" href={`mailto:${CONTACT.email}?subject=AI%20agent%20enquiry`} data-cursor="Say hi">
              <span>Let&apos;s talk</span>
            </a>
          </Magnetic>
        </div>
        <div className="cta__contacts">
          <a href={`tel:${CONTACT.phone.replace(/-/g, '')}`} className="link-u">{CONTACT.phone}</a>
          <a href={`mailto:${CONTACT.email}`} className="link-u">{CONTACT.email}</a>
          <a href={`https://wa.me/${CONTACT.phone.replace(/\D/g, '')}`} className="link-u" target="_blank" rel="noreferrer">WhatsApp us</a>
        </div>
      </div>
    </section>
  )
}
