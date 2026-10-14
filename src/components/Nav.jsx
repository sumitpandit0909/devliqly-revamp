import { useEffect, useRef, useState } from 'react'
import { gsap, ScrollTrigger, useGSAP, scrollToHash, lenisRef } from '../lib/motion'
import { NAV } from '../data'
import Logo from './Logo'
import Magnetic from './Magnetic'

export default function Nav() {
  const root = useRef(null)
  const [open, setOpen] = useState(false)

  useGSAP(() => {
    // Hide on scroll down, reveal on scroll up; solid background after the hero
    ScrollTrigger.create({
      start: 0,
      end: 'max',
      onUpdate: (self) => {
        const y = self.scroll()
        root.current.classList.toggle('is-solid', y > 40)
        root.current.classList.toggle('is-hidden', self.direction === 1 && y > 300)
      },
    })
    gsap.to('.progress i', {
      scaleX: 1,
      ease: 'none',
      scrollTrigger: { start: 0, end: 'max', scrub: 0.3 },
    })
  })

  useEffect(() => {
    if (open) lenisRef.current?.stop()
    else lenisRef.current?.start()
    document.body.style.overflow = open ? 'hidden' : ''
    if (open) gsap.fromTo('.menu__link', { yPercent: 120 }, { yPercent: 0, stagger: 0.06, duration: 0.8, ease: 'power4.out', delay: 0.2 })
  }, [open])

  const go = (e, href) => {
    e.preventDefault()
    setOpen(false)
    scrollToHash(href)
  }

  return (
    <>
      <div className="progress" aria-hidden="true"><i /></div>
      <header className={`nav ${open ? 'is-open' : ''}`} ref={root}>
        <a href="#top" className="nav__logo" onClick={(e) => go(e, '#top')} aria-label="Devliqly home">
          <Logo />
        </a>
        <nav className="nav__links" aria-label="Primary">
          {NAV.map((n) => (
            <a key={n.href} href={n.href} onClick={(e) => go(e, n.href)} className="nav__link">
              <span data-text={n.label}>{n.label}</span>
            </a>
          ))}
        </nav>
        <Magnetic>
          <a href="#contact" onClick={(e) => go(e, '#contact')} className="btn btn--small nav__cta">
            Book a demo
          </a>
        </Magnetic>
        <button
          className="nav__burger"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
        >
          <i /><i />
        </button>
      </header>

      <div className={`menu ${open ? 'is-open' : ''}`} aria-hidden={!open}>
        <nav className="menu__inner">
          {NAV.concat({ label: 'Contact', href: '#contact' }).map((n, i) => (
            <div className="menu__mask" key={n.href}>
              <a className="menu__link" href={n.href} onClick={(e) => go(e, n.href)} tabIndex={open ? 0 : -1}>
                <sup>0{i + 1}</sup>{n.label}
              </a>
            </div>
          ))}
        </nav>
      </div>
    </>
  )
}
