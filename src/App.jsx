import { useCallback, useEffect, useState } from 'react'
import Lenis from 'lenis'
import { gsap, ScrollTrigger, lenisRef, prefersReducedMotion, scrollToHash } from './lib/motion'
import Preloader from './components/Preloader'
import Cursor from './components/Cursor'
import Nav from './components/Nav'
import Hero from './components/Hero'
import Marquee from './components/Marquee'
import Statement from './components/Statement'
import Services from './components/Services'
import CallDemo from './components/CallDemo'
import Process from './components/Process'
import Stats from './components/Stats'
import Integrations from './components/Integrations'
import Testimonials from './components/Testimonials'
import Faq from './components/Faq'
import Cta from './components/Cta'
import Footer from './components/Footer'
import DemoModal from './components/DemoModal'
import { DemoContext } from './lib/demo'

export default function App() {
  const [loaded, setLoaded] = useState(false)
  const [demo, setDemo] = useState({ open: false, service: '' })
  const openDemo = useCallback((service = '') => setDemo({ open: true, service: typeof service === 'string' ? service : '' }), [])
  const closeDemo = useCallback(() => setDemo((d) => ({ ...d, open: false })), [])

  useEffect(() => {
    if (prefersReducedMotion()) return
    const lenis = new Lenis({ lerp: 0.09, smoothWheel: true })
    lenisRef.current = lenis
    lenis.on('scroll', ScrollTrigger.update)
    const tick = (time) => lenis.raf(time * 1000)
    gsap.ticker.add(tick)
    gsap.ticker.lagSmoothing(0)
    return () => {
      gsap.ticker.remove(tick)
      lenis.destroy()
      lenisRef.current = null
    }
  }, [])

  // Route all in-page anchor clicks through the smooth scroller
  useEffect(() => {
    const onClick = (e) => {
      const a = e.target.closest('a[href^="#"]')
      if (!a || e.defaultPrevented) return
      const hash = a.getAttribute('href')
      if (hash.length < 2) return
      e.preventDefault()
      scrollToHash(hash)
    }
    document.addEventListener('click', onClick)
    return () => document.removeEventListener('click', onClick)
  }, [])

  // Lock scrolling while the preloader is up
  useEffect(() => {
    const lenis = lenisRef.current
    if (!loaded) {
      lenis?.stop()
      document.documentElement.classList.add('is-loading')
    } else {
      lenis?.start()
      document.documentElement.classList.remove('is-loading')
      ScrollTrigger.refresh()
    }
  }, [loaded])

  return (
    <DemoContext.Provider value={openDemo}>
      <Preloader onDone={() => setLoaded(true)} />
      <Cursor />
      <div className="grain" aria-hidden="true" />
      <Nav />
      <main>
        <Hero ready={loaded} />
        <Marquee />
        <Statement />
        <Services />
        <CallDemo />
        <Process />
        <Stats />
        <Integrations />
        <Testimonials />
        <Faq />
        <Cta />
      </main>
      <Footer />
      <DemoModal open={demo.open} service={demo.service} onClose={closeDemo} />
    </DemoContext.Provider>
  )
}
