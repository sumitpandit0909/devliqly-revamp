import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { SERVICES } from '../data'
import ServiceVisual from './ServiceVisual'

export default function Services() {
  const root = useRef(null)
  const track = useRef(null)
  const counter = useRef(null)

  useGSAP(() => {
    if (prefersReducedMotion()) return
    const mm = gsap.matchMedia()

    // Desktop: pin the section and translate the card track horizontally
    mm.add('(min-width: 900px)', () => {
      const distance = () => track.current.scrollWidth - window.innerWidth
      const horizontal = gsap.to(track.current, {
        x: () => -distance(),
        ease: 'none',
        scrollTrigger: {
          trigger: '.services__pin',
          pin: true,
          scrub: 1,
          start: 'top top',
          end: () => '+=' + distance(),
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            const i = Math.min(SERVICES.length, Math.max(1, Math.ceil(self.progress * SERVICES.length + 0.001)))
            counter.current.textContent = String(i).padStart(2, '0')
          },
        },
      })
      gsap.to('.services__progress i', {
        scaleX: 1, ease: 'none',
        scrollTrigger: { trigger: '.services__pin', start: 'top top', end: () => '+=' + distance(), scrub: true, invalidateOnRefresh: true },
      })

      // Inner parallax: each card's visual pieces drift at different rates while the track moves
      gsap.utils.toArray('.svc').forEach((card) => {
        gsap.fromTo(card.querySelector('.svc__visual'), { xPercent: 12 }, {
          xPercent: -12, ease: 'none',
          scrollTrigger: { trigger: card, containerAnimation: horizontal, start: 'left right', end: 'right left', scrub: true },
        })
        card.querySelectorAll('[data-par]').forEach((el) => {
          const p = Number(el.dataset.par)
          gsap.fromTo(el, { x: 40 * p }, {
            x: -40 * p, ease: 'none',
            scrollTrigger: { trigger: card, containerAnimation: horizontal, start: 'left right', end: 'right left', scrub: true },
          })
        })
        gsap.from(card.querySelectorAll('.svc__title, .svc__desc, .svc__points li'), {
          y: 40, autoAlpha: 0, stagger: 0.06, duration: 0.8, ease: 'power3.out',
          scrollTrigger: { trigger: card, containerAnimation: horizontal, start: 'left 75%' },
        })
      })
      gsap.to('.services__bgword', {
        xPercent: -40, ease: 'none',
        scrollTrigger: { trigger: '.services__pin', start: 'top top', end: () => '+=' + distance(), scrub: true, invalidateOnRefresh: true },
      })
    })

    // Mobile: stacked cards fade and rise in
    mm.add('(max-width: 899px)', () => {
      gsap.utils.toArray('.svc').forEach((card) => {
        gsap.from(card, { y: 80, autoAlpha: 0, duration: 1, ease: 'power3.out', scrollTrigger: { trigger: card, start: 'top 85%' } })
      })
    })

    gsap.from('.services__head > *', {
      y: 50, autoAlpha: 0, stagger: 0.1, duration: 1, ease: 'power3.out',
      scrollTrigger: { trigger: root.current, start: 'top 70%' },
    })
  }, { scope: root })

  return (
    <section className="services" id="services" ref={root}>
      <div className="services__pin">
        <div className="services__bgword" aria-hidden="true">AGENTS · AGENTS · AGENTS</div>
        <div className="services__head container">
          <p className="label">( Services )</p>
          <h2 className="h2">Five ways AI <em>works</em> for your business</h2>
          <div className="services__meta">
            <span className="services__count"><b ref={counter}>01</b> / 0{SERVICES.length}</span>
            <span className="services__progress"><i /></span>
          </div>
        </div>
        <div className="services__track" ref={track}>
          {SERVICES.map((s) => (
            <article className="svc" key={s.id} id={`svc-${s.id}`} data-cursor="Explore">
              <div className="svc__top">
                <span className="svc__no">{s.no}</span>
                <span className="svc__tag label">{s.tag}</span>
              </div>
              <div className="svc__visual"><ServiceVisual type={s.visual} /></div>
              <h3 className="svc__title">{s.title}</h3>
              <p className="svc__desc">{s.desc}</p>
              <ul className="svc__points">
                {s.points.map((p) => <li key={p}>{p}</li>)}
              </ul>
            </article>
          ))}
          <div className="svc svc--end">
            <p className="h2">Need something <em>different?</em></p>
            <p className="svc__desc">If it involves a conversation or a repetitive task, we can build an agent for it.</p>
            <a href="#contact" className="btn">Tell us your use case</a>
          </div>
        </div>
      </div>
    </section>
  )
}
