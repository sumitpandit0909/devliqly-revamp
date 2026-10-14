import { useEffect, useRef, useState } from 'react'
import { gsap, useGSAP, scrollToHash, prefersReducedMotion } from '../lib/motion'
import Magnetic from './Magnetic'
import HeroField from './HeroField'

const LINES = [
  ['AI agents that'],
  [<em key="t">talk, listen</em>],
  ['& work for you.'],
]

const CAPTIONS = [
  { who: 'Caller', text: 'Hi, can I move my appointment to tomorrow evening?' },
  { who: 'Agent', text: 'Of course. 4:30 PM is free. Shall I book it?' },
  { who: 'Caller', text: 'Yes please, and send me a reminder.' },
  { who: 'Agent', text: 'Done! Confirmation sent on WhatsApp. ✓' },
]

const CHIPS = [
  { text: 'Inbound call answered', meta: '0.6s', cls: 'chip--a', depth: 0.9 },
  { text: 'Ticket #4821 resolved', meta: 'Auto', cls: 'chip--b', depth: 1.4 },
  { text: 'Lead qualified → CRM', meta: 'Hot', cls: 'chip--c', depth: 1.1 },
]

const PROOF = [
  ['24/7', 'always on'],
  ['<1s', 'response'],
  ['40+', 'languages'],
]

export default function Hero({ ready }) {
  const root = useRef(null)
  const intro = useRef(null)
  const [cap, setCap] = useState(0)

  // Cycle the live transcript captions
  useEffect(() => {
    const id = setInterval(() => setCap((c) => (c + 1) % CAPTIONS.length), 2800)
    return () => clearInterval(id)
  }, [])

  useGSAP(() => {
    if (prefersReducedMotion()) return
    intro.current = gsap.timeline({ paused: true, defaults: { ease: 'power4.out' } })
      .from('.hero__line > span', { yPercent: 110, stagger: 0.1, duration: 1.2 })
      .from('.hero__eyebrow, .hero__sub, .hero__actions, .hero__proof', { y: 24, autoAlpha: 0, stagger: 0.08, duration: 0.9 }, '-=0.85')
      .from('.console__body', { y: 60, rotateX: 18, autoAlpha: 0, duration: 1.4, ease: 'expo.out' }, 0.25)
      .from('.chip', { scale: 0.6, autoAlpha: 0, stagger: 0.12, duration: 0.9, ease: 'back.out(1.8)' }, 0.8)
      .from('.hero__aurora i', { scale: 0.5, autoAlpha: 0, stagger: 0.15, duration: 2, ease: 'expo.out' }, 0)

    // Scroll parallax: copy lifts away, console tilts back and lags, chips drift at their own rates
    const st = { trigger: root.current, start: 'top top', end: 'bottom top', scrub: true }
    gsap.to('.hero__copy', { yPercent: -18, autoAlpha: 0, ease: 'none', scrollTrigger: st })
    gsap.to('.console', { yPercent: 14, rotateX: -14, scale: 0.92, ease: 'none', scrollTrigger: st })
    gsap.to('.hero__aurora', { yPercent: 35, ease: 'none', scrollTrigger: st })
    gsap.to('.hero__field', { yPercent: 18, ease: 'none', scrollTrigger: st })
    gsap.matchMedia().add('(min-width: 900px)', () => {
      gsap.utils.toArray('.chip').forEach((chip) => {
        gsap.to(chip, { y: () => -window.innerHeight * 0.25 * Number(chip.dataset.speed), ease: 'none', scrollTrigger: st })
      })
    })
  }, { scope: root })

  useEffect(() => {
    if (ready) intro.current?.play()
  }, [ready])

  // Pointer parallax on layered elements + subtle 3D tilt of the console
  useEffect(() => {
    if (!window.matchMedia('(hover: hover)').matches || prefersReducedMotion()) return
    const layers = gsap.utils.toArray('[data-depth]', root.current).map((el) => ({
      d: Number(el.dataset.depth),
      x: gsap.quickTo(el, 'x', { duration: 1.2, ease: 'power3' }),
      y: gsap.quickTo(el, 'y', { duration: 1.2, ease: 'power3' }),
    }))
    const tilt = root.current.querySelector('.console__tilt')
    const rx = gsap.quickTo(tilt, 'rotateX', { duration: 1, ease: 'power3' })
    const ry = gsap.quickTo(tilt, 'rotateY', { duration: 1, ease: 'power3' })
    const move = (e) => {
      const nx = e.clientX / window.innerWidth - 0.5
      const ny = e.clientY / window.innerHeight - 0.5
      layers.forEach((l) => { l.x(nx * l.d * 40); l.y(ny * l.d * 40) })
      rx(ny * -8)
      ry(nx * 10)
    }
    window.addEventListener('pointermove', move)
    return () => window.removeEventListener('pointermove', move)
  }, [])

  const go = (hash) => (e) => { e.preventDefault(); scrollToHash(hash) }

  return (
    <section className="hero" id="top" ref={root}>
      <div className="hero__bg" aria-hidden="true">
        <HeroField />
        <div className="hero__aurora">
          <i className="a1" data-depth="-0.8" />
          <i className="a2" data-depth="0.6" />
          <i className="a3" data-depth="-0.4" />
        </div>
      </div>

      <div className="hero__inner">
        <div className="hero__copy">
          <p className="hero__eyebrow">
            <span className="pulse" />
            <span>AI agent studio</span>
            <span className="hero__eyebrow-sep" />
            <span className="hero__eyebrow-muted">Now booking Q4 projects</span>
          </p>
          <h1 className="hero__title">
            {LINES.map((parts, i) => (
              <span className="hero__line" key={i}><span>{parts}</span></span>
            ))}
          </h1>
          <p className="hero__sub">
            Chatbots, customer service agents, call agents, voice agents and custom workflows,
            designed and deployed by Devliqly so every customer gets an answer around the clock.
          </p>
          <div className="hero__actions">
            <Magnetic>
              <a href="#contact" className="btn" onClick={go('#contact')}>
                Book a free demo <Arrow />
              </a>
            </Magnetic>
            <a href="#services" className="btn btn--ghost" onClick={go('#services')}>
              Explore services
            </a>
          </div>
          <ul className="hero__proof">
            {PROOF.map(([n, l]) => (
              <li key={l}><b>{n}</b><span>{l}</span></li>
            ))}
          </ul>
        </div>

        <div className="hero__stage" aria-hidden="true">
          <div className="console">
            <div className="console__tilt">
              <div className="console__body">
                <div className="console__head">
                  <span className="console__live"><i /> Live</span>
                  <span>Voice agent · Inbound</span>
                  <span className="console__time">00:42</span>
                </div>

                <div className="console__orb">
                  <div className="orb">
                    <div className="orb__ring orb__ring--1" />
                    <div className="orb__ring orb__ring--2" />
                    <div className="orb__ring orb__ring--3" />
                    <div className="orb__core">
                      <div className="wave">
                        {Array.from({ length: 11 }).map((_, i) => <i key={i} style={{ '--i': i }} />)}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="console__wave">
                  {Array.from({ length: 48 }).map((_, i) => <i key={i} style={{ '--i': i }} />)}
                </div>

                <div className="console__caption">
                  <div key={cap} className="caption">
                    <small className={CAPTIONS[cap].who === 'Agent' ? 'is-agent' : ''}>{CAPTIONS[cap].who}</small>
                    <p>{CAPTIONS[cap].text}</p>
                  </div>
                </div>

                <div className="console__foot">
                  {['Chat', 'Support', 'Calls', 'Voice', 'Workflows'].map((t, i) => (
                    <span key={t} className={i === 3 ? 'is-on' : ''}>{t}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {CHIPS.map((c) => (
            <div key={c.text} className={`chip ${c.cls}`} data-speed={c.depth}>
              <div className="chip__inner" data-depth={c.depth}>
                <span className="chip__dot" />
                <span>{c.text}</span>
                <b>{c.meta}</b>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="hero__scroll label" aria-hidden="true">
        <span>Scroll</span>
        <i />
      </div>
    </section>
  )
}

export function Arrow() {
  return (
    <svg className="arrow" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path d="M6 18L18 6M18 6H8M18 6v10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}
