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
import { setPageMeta } from '../lib/router'

export default function Home({ ready }) {
  useEffect(() => {
    setPageMeta(
      'DEVLIQLY | AI Agents That Work For You',
      'Devliqly builds AI agents that talk, listen and work for your business: chatbot integration, customer service agents, inbound and outbound call agents, voice agents and custom agent workflows.',
    )
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
