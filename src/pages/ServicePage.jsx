import { useEffect, useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { setPageMeta } from '../lib/router'
import { useOpenDemo } from '../lib/demo'
import { SERVICES } from '../data'
import { SERVICE_DETAILS } from '../serviceDetails'
import ServiceVisual from '../components/ServiceVisual'
import Magnetic from '../components/Magnetic'
import Faq from '../components/Faq'
import Cta from '../components/Cta'
import { Arrow } from '../components/Hero'

export default function ServicePage({ service }) {
  const root = useRef(null)
  const openDemo = useOpenDemo()
  const d = SERVICE_DETAILS[service.id]
  const others = SERVICES.filter((s) => s.id !== service.id)
  const longestWord = Math.max(...d.headline.join(' ').split(' ').map((w) => w.length))

  useEffect(() => {
    setPageMeta(`${service.title} | DEVLIQLY`, d.intro)
  }, [service, d])

  useGSAP(() => {
    if (prefersReducedMotion()) return
    gsap.from('.sp-title__line > span', { yPercent: 110, stagger: 0.08, duration: 1.1, ease: 'power4.out', delay: 0.1 })
    gsap.from('.sp-hero__meta, .sp-intro, .sp-actions', { y: 30, autoAlpha: 0, stagger: 0.08, duration: 0.9, ease: 'power3.out', delay: 0.35 })
    gsap.from('.sp-visual', { y: 60, autoAlpha: 0, scale: 0.94, duration: 1.2, ease: 'power3.out', delay: 0.3 })

    // Parallax: the visual drifts up and the giant number drifts sideways as the hero scrolls away
    gsap.to('.sp-visual', { yPercent: -18, ease: 'none', scrollTrigger: { trigger: '.sp-hero', start: 'top top', end: 'bottom top', scrub: true } })
    gsap.to('.sp-hero__no', { xPercent: -25, ease: 'none', scrollTrigger: { trigger: '.sp-hero', start: 'top top', end: 'bottom top', scrub: true } })

    gsap.utils.toArray('.sp-reveal').forEach((group) => {
      gsap.from(group.children, { y: 50, autoAlpha: 0, stagger: 0.08, duration: 0.9, ease: 'power3.out', scrollTrigger: { trigger: group, start: 'top 82%' } })
    })
    gsap.from('.sp-steps__rail i', { scaleX: 0, ease: 'none', scrollTrigger: { trigger: '.sp-steps__list', start: 'top 75%', end: 'bottom 60%', scrub: true } })
    gsap.to('.sp-tools__track', { xPercent: -30, ease: 'none', scrollTrigger: { trigger: '.sp-tools', start: 'top bottom', end: 'bottom top', scrub: true } })
  }, { scope: root, dependencies: [service.id] })

  return (
    <main ref={root}>
      <section className="sp-hero">
        <div className="sp-hero__glow" aria-hidden="true" />
        <div className="sp-hero__no" aria-hidden="true">{service.no}</div>
        <div className="container sp-hero__grid">
          <div className="sp-hero__copy">
            <div className="sp-hero__meta">
              <a href="/#services" className="label sp-back">← All services</a>
              <span className="label">{service.tag}</span>
            </div>
            <h1 className="sp-title" style={{ '--fit': longestWord }}>
              {d.headline.map((line, i) => (
                <span className="sp-title__line" key={line}>
                  <span>{i === 1 ? <em>{line}</em> : line}</span>
                </span>
              ))}
            </h1>
            <p className="lead sp-intro">{d.intro}</p>
            <div className="sp-actions">
              <Magnetic>
                <button type="button" className="btn" onClick={() => openDemo(service.title)}>
                  Book a free demo <Arrow />
                </button>
              </Magnetic>
              <a href="#contact-form" className="btn btn--ghost">Ask a question</a>
            </div>
          </div>
          <div className="sp-visual">
            <div className="sp-visual__frame">
              <ServiceVisual type={service.visual} />
            </div>
            <ul className="sp-visual__points">
              {service.points.map((p) => <li key={p}>{p}</li>)}
            </ul>
          </div>
        </div>
      </section>

      <section className="section sp-features">
        <div className="container">
          <div className="section-head">
            <p className="label">( What you get )</p>
            <h2 className="h2">Built to <em>deliver</em></h2>
          </div>
          <div className="sp-features__grid sp-reveal">
            {d.features.map((f, i) => (
              <article className="sp-feature" key={f.title}>
                <span className="sp-feature__no">{String(i + 1).padStart(2, '0')}</span>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section sp-uses">
        <div className="container sp-uses__grid">
          <div className="sp-uses__head">
            <p className="label">( Use cases )</p>
            <h2 className="h2">Where it <em>fits</em></h2>
          </div>
          <ul className="sp-uses__list sp-reveal">
            {d.useCases.map((u) => (
              <li key={u.title}>
                <h3>{u.title}</h3>
                <p>{u.desc}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="section sp-steps">
        <div className="container">
          <div className="section-head">
            <p className="label">( How we build it )</p>
            <h2 className="h2">From call to <em>live</em></h2>
          </div>
          <div className="sp-steps__rail" aria-hidden="true"><i /></div>
          <ol className="sp-steps__list sp-reveal">
            {d.steps.map((s, i) => (
              <li key={s.title}>
                <span className="sp-steps__no">0{i + 1}</span>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="sp-tools" aria-label="Works with">
        <div className="sp-tools__track">
          {[...d.tools, ...d.tools].map((t, i) => (
            <span className="sp-tools__item" key={i} aria-hidden={i >= d.tools.length}>{t}</span>
          ))}
        </div>
      </section>

      <Faq items={d.faqs} title={<>Good <em>questions</em></>} />

      <section className="section sp-next">
        <div className="container">
          <p className="label">( More services )</p>
          <ul className="sp-next__list">
            {others.map((s) => (
              <li key={s.id}>
                <a href={`/services/${s.slug}`} className="sp-next__link" data-cursor="Explore">
                  <span className="sp-next__no">{s.no}</span>
                  <span className="sp-next__title">{s.title}</span>
                  <span className="sp-next__tag label">{s.tag}</span>
                  <Arrow />
                </a>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <Cta />
    </main>
  )
}
