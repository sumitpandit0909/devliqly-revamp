import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import Lenis from 'lenis'
import { gsap, ScrollTrigger, lenisRef, prefersReducedMotion, scrollToHash } from './lib/motion'
import Preloader from './components/Preloader'
import Cursor from './components/Cursor'
import Nav from './components/Nav'
import Footer from './components/Footer'
import DemoModal from './components/DemoModal'
import Home from './pages/Home'
import ServicePage from './pages/ServicePage'
import LegalPage from './pages/LegalPage'
import NotFound from './pages/NotFound'
import { DemoContext } from './lib/demo'
import { navigate, usePath } from './lib/router'
import { SERVICES } from './data'
import { LEGAL } from './legal'

function route(path, loaded) {
  if (path === '/') return <Home ready={loaded} />
  const service = SERVICES.find((s) => path === `/services/${s.slug}`)
  if (service) return <ServicePage key={service.id} service={service} />
  const legal = Object.values(LEGAL).find((l) => l.path === path)
  if (legal) return <LegalPage key={legal.path} doc={legal} />
  return <NotFound />
}

export default function App() {
  const [loaded, setLoaded] = useState(false)
  const [demo, setDemo] = useState({ open: false, service: '' })
  const openDemo = useCallback((service = '') => setDemo({ open: true, service: typeof service === 'string' ? service : '' }), [])
  const closeDemo = useCallback(() => setDemo((d) => ({ ...d, open: false })), [])
  const path = usePath().replace(/(.)\/+$/, '$1')
  const firstRoute = useRef(true)

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

  // Route in-page anchors through the smooth scroller and internal page links through the router
  useEffect(() => {
    const onClick = (e) => {
      const a = e.target.closest('a[href^="#"], a[href^="/"]')
      if (!a || e.defaultPrevented) return
      const href = a.getAttribute('href')
      if (href.startsWith('#')) {
        if (href.length < 2) return
        e.preventDefault()
        scrollToHash(href)
        return
      }
      if (href.startsWith('//') || a.target || a.hasAttribute('download') || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
      e.preventDefault()
      navigate(href)
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
      // Deep links such as /#faq land on their section once the page is ready
      if (window.location.hash.length > 1) scrollToHash(window.location.hash)
    }
  }, [loaded])

  useEffect(() => {
    window.history.scrollRestoration = 'manual'
  }, [])

  // On page change: jump to the top before paint, then scroll to the hash once the new page has laid out
  useLayoutEffect(() => {
    if (firstRoute.current) {
      firstRoute.current = false
      return
    }
    lenisRef.current?.scrollTo(0, { immediate: true, force: true })
    window.scrollTo(0, 0)
    // Give the new page a moment to mount its pins, then re-measure before scrolling to a hash
    const timer = setTimeout(() => {
      ScrollTrigger.refresh()
      lenisRef.current?.resize()
      if (window.location.hash.length > 1) scrollToHash(window.location.hash)
    }, 120)
    return () => clearTimeout(timer)
  }, [path])

  return (
    <DemoContext.Provider value={openDemo}>
      <Preloader onDone={() => setLoaded(true)} />
      <Cursor />
      <div className="grain" aria-hidden="true" />
      <Nav />
      {route(path, loaded)}
      <Footer />
      <DemoModal open={demo.open} service={demo.service} onClose={closeDemo} />
    </DemoContext.Provider>
  )
}
