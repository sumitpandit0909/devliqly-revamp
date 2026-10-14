import { useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { CALL_SCRIPT } from '../data'

const STEPS = [
  { k: 'Listens', d: 'Real-time speech recognition that understands accents, Hinglish and interruptions.' },
  { k: 'Understands', d: 'An LLM brain trained on your business works out intent and pulls live data from your systems.' },
  { k: 'Acts', d: 'It books, updates, sends and escalates in your tools while the call is still going.' },
]

export default function CallDemo() {
  const root = useRef(null)

  useGSAP(() => {
    if (prefersReducedMotion()) return
    const mm = gsap.matchMedia()
    mm.add('(min-width: 900px)', () => {
      const tl = gsap.timeline({
        defaults: { ease: 'power2.out' },
        scrollTrigger: { trigger: root.current, pin: '.demo__pin', start: 'top top', end: '+=220%', scrub: 1 },
      })
      tl.from('.phone', { yPercent: 30, rotate: -8, autoAlpha: 0, duration: 1 })
      gsap.utils.toArray('.msg').forEach((m, i) => {
        tl.from(m, { y: 30, autoAlpha: 0, scale: 0.92, duration: 0.6 }, 1 + i * 0.8)
      })
      gsap.utils.toArray('.demo__step').forEach((s, i) => {
        tl.to(s, { opacity: 1, duration: 0.3 }, 0.8 + i * 1.3)
        tl.to(s.querySelector('.demo__fill'), { scaleY: 1, duration: 1.3, ease: 'none' }, 0.8 + i * 1.3)
        if (i < 2) tl.to(s, { opacity: 0.3, duration: 0.3 }, 2.1 + i * 1.3)
      })
      const timer = root.current.querySelector('.phone__timer')
      const secs = { v: 0 }
      tl.to(secs, {
        v: 72, ease: 'none', duration: 5,
        onUpdate: () => {
          const s = Math.round(secs.v)
          timer.textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
        },
      }, 0)
      tl.to('.phone', { rotate: 3, duration: 5, ease: 'none' }, 0)
    })
    mm.add('(max-width: 899px)', () => {
      gsap.from('.msg', { y: 30, autoAlpha: 0, stagger: 0.25, duration: 0.7, scrollTrigger: { trigger: '.phone', start: 'top 70%' } })
      gsap.utils.toArray('.demo__step').forEach((s) => gsap.to(s, { opacity: 1, scrollTrigger: { trigger: s, start: 'top 80%', end: 'top 50%', scrub: true } }))
    })
  }, { scope: root })

  return (
    <section className="demo" id="demo" ref={root}>
      <div className="demo__pin container">
        <div className="demo__copy">
          <p className="label">( How a call agent works )</p>
          <h2 className="h2">A real conversation, <em>handled end-to-end</em></h2>
          <ol className="demo__steps">
            {STEPS.map((s, i) => (
              <li className="demo__step" key={s.k}>
                <span className="demo__line"><i className="demo__fill" /></span>
                <div>
                  <h3><span>0{i + 1}</span>{s.k}</h3>
                  <p>{s.d}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="demo__stage">
          <div className="phone" aria-label="Example call transcript">
            <div className="phone__notch" />
            <div className="phone__head">
              <div className="phone__avatar"><div className="wave wave--sm">{Array.from({ length: 7 }).map((_, i) => <i key={i} style={{ '--i': i }} />)}</div></div>
              <div>
                <b>Devliqly Voice Agent</b>
                <span>Inbound call · <span className="phone__timer">00:00</span></span>
              </div>
            </div>
            <div className="phone__body">
              {CALL_SCRIPT.map((m, i) => (
                <div key={i} className={`msg msg--${m.who}`}>
                  {m.who !== 'system' && <small>{m.who === 'agent' ? 'AI Agent' : 'Caller'}</small>}
                  {m.text}
                </div>
              ))}
            </div>
            <div className="phone__controls">
              <span /><span className="end" /><span />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
