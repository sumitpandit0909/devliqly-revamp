import { useEffect, useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { setPageMeta } from '../lib/router'
import { LEGAL } from '../legal'

const slug = (h) => h.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

export default function LegalPage({ doc }) {
  const root = useRef(null)
  const other = Object.values(LEGAL).find((l) => l !== doc)

  useEffect(() => {
    setPageMeta(`${doc.title} | DEVLIQLY`, doc.intro)
  }, [doc])

  useGSAP(() => {
    if (prefersReducedMotion()) return
    gsap.from('.legal__head > *', { y: 40, autoAlpha: 0, stagger: 0.08, duration: 1, ease: 'power3.out', delay: 0.1 })
    gsap.utils.toArray('.legal__section').forEach((el) => {
      gsap.from(el, { y: 30, autoAlpha: 0, duration: 0.8, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 88%' } })
    })
  }, { scope: root, dependencies: [doc.path] })

  return (
    <main className="legal" ref={root}>
      <div className="container">
        <header className="legal__head">
          <p className="label">( Legal )</p>
          <h1 className="legal__title">{doc.title}</h1>
          <p className="label legal__updated">Last updated: {doc.updated}</p>
          <p className="lead legal__intro">{doc.intro}</p>
        </header>

        <div className="legal__grid">
          <nav className="legal__toc" aria-label="On this page">
            <p className="label">On this page</p>
            <ol>
              {doc.sections.map((s) => (
                <li key={s.h}><a href={`#${slug(s.h)}`}>{s.h}</a></li>
              ))}
            </ol>
            <a href={other.path} className="legal__switch link-u">Read our {other.title} →</a>
          </nav>

          <div className="legal__body">
            {doc.sections.map((s, i) => (
              <section className="legal__section" id={slug(s.h)} key={s.h} data-scroll-offset="-80">
                <h2><span>{String(i + 1).padStart(2, '0')}</span>{s.h}</h2>
                {s.body.map((b, j) => (Array.isArray(b)
                  ? <ul key={j}>{b.map((item) => <li key={item}>{item}</li>)}</ul>
                  : <p key={j}>{b}</p>))}
              </section>
            ))}
          </div>
        </div>
      </div>
    </main>
  )
}
