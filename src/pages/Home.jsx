import { useEffect } from 'react'
import Hero from '../components/Hero'
import Marquee from '../components/Marquee'
import Statement from '../components/Statement'
import Services from '../components/Services'
import CallDemo from '../components/CallDemo'
import Process from '../components/Process'
import Stats from '../components/Stats'
import Integrations from '../components/Integrations'
import Testimonials from '../components/Testimonials'
import Faq from '../components/Faq'
import Cta from '../components/Cta'
import { applyMeta, homeMeta } from '../lib/seo'

export default function Home({ ready }) {
  useEffect(() => {
    applyMeta(homeMeta())
  }, [])

  return (
    <main>
      <Hero ready={ready} />
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
  )
}
