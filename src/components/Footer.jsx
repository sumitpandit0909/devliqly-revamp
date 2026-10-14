import { useEffect, useRef } from 'react'
import { gsap, useGSAP, prefersReducedMotion } from '../lib/motion'
import { CONTACT, SERVICES } from '../data'
import Logo from './Logo'

export default function Footer() {
  const root = useRef(null)
  const big = useRef(null)

  // Size the wordmark so it always spans the container edge to edge, whatever the font metrics
  useEffect(() => {
    const el = big.current
    const fit = () => {
      el.style.fontSize = '100px'
      const natural = [...el.children].reduce((w, c) => w + c.getBoundingClientRect().width, 0)
      if (natural) el.style.fontSize = `${(100 * el.clientWidth) / natural}px`
    }
    fit()
    document.fonts?.ready.then(fit)
    const ro = new ResizeObserver(fit)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useGSAP(() => {
    if (prefersReducedMotion()) return
    // Footer content slides up from beneath as it comes into view
    gsap.from('.footer__inner', { yPercent: -40, ease: 'none', scrollTrigger: { trigger: root.current, start: 'top bottom', end: 'bottom bottom', scrub: true } })
    gsap.from('.footer__big span', { yPercent: 100, stagger: 0.04, ease: 'power3.out', duration: 1, scrollTrigger: { trigger: '.footer__big', start: 'top 95%' } })
  }, { scope: root })

  return (
    <footer className="footer" ref={root}>
      <div className="footer__inner container">
        <div className="footer__cols">
          <div className="footer__brand">
            <Logo />
            <p>We build your imagination, and now the AI agents that run it.</p>
          </div>
          <div>
            <h4 className="label">Services</h4>
            {SERVICES.map((s) => <a key={s.id} href="#services">{s.title}</a>)}
          </div>
          <div>
            <h4 className="label">Quick links</h4>
            <a href="https://www.devliqly.in/blogs">Blog</a>
            <a href="#faq">FAQ</a>
            <a href="#">Terms &amp; Conditions</a>
            <a href="#">Privacy Policy</a>
          </div>
          <div>
            <h4 className="label">Contact</h4>
            <a href={`tel:${CONTACT.phone.replace(/-/g, '')}`}>{CONTACT.phone}</a>
            <a href={`mailto:${CONTACT.email}`}>{CONTACT.email}</a>
            <div className="footer__social">
              <a href="https://www.linkedin.com/" aria-label="LinkedIn">in</a>
              <a href="https://www.twitter.com/" aria-label="Twitter">x</a>
              <a href="https://www.facebook.com/" aria-label="Facebook">f</a>
            </div>
          </div>
        </div>
        <div className="footer__big" ref={big} aria-hidden="true">
          {'DEVLIQLY'.split('').map((c, i) => <span key={i}>{c}</span>)}
        </div>
        <div className="footer__bottom">
          <span>© {new Date().getFullYear()} Devliqly. All rights reserved.</span>
          <a href="#top">Back to top ↑</a>
        </div>
      </div>
    </footer>
  )
}
