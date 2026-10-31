export const NAV = [
  { label: 'Services', href: '#services' },
  { label: 'How it works', href: '#demo' },
  { label: 'Process', href: '#process' },
  { label: 'Clients', href: '#clients' },
  { label: 'FAQ', href: '#faq' },
  { label: 'Contact', href: '#contact-form' },
]

export const SERVICES = [
  {
    id: 'chatbot',
    no: '01',
    title: 'Chatbot Integration',
    tag: 'Web · WhatsApp · Instagram',
    desc: 'AI chatbots trained on your business and connected to your website, WhatsApp, Instagram and Messenger. They answer questions, capture leads and book appointments 24/7.',
    points: ['Trained on your docs & FAQs', 'Lead capture to your CRM', 'Multilingual, incl. Hindi & Hinglish'],
    visual: 'chat',
  },
  {
    id: 'support',
    no: '02',
    title: 'Customer Service Agent',
    tag: 'Support · Helpdesk · Tickets',
    desc: 'An AI support agent that resolves common tickets on its own: order status, refunds, troubleshooting. It hands complex cases to your team along with the full context.',
    points: ['Resolves up to 70% of routine tickets', 'Works inside your helpdesk', 'Human handoff with summaries'],
    visual: 'support',
  },
  {
    id: 'calls',
    no: '03',
    title: 'Inbound & Outbound Call Agents',
    tag: 'Telephony · IVR · Campaigns',
    desc: 'Phone agents that pick up every inbound call and run outbound campaigns for lead follow-ups, reminders, surveys and collections, with natural conversation in place of a robotic IVR.',
    points: ['Unlimited concurrent calls', 'Call recording, transcripts & sentiment', 'Smart transfer to live agents'],
    visual: 'calls',
  },
  {
    id: 'voice',
    no: '04',
    title: 'Voice Agents',
    tag: 'Real-time · Low latency',
    desc: 'Lifelike, low-latency voice AI for your app, kiosk or website. Custom voices, interruption handling and real-time actions while the conversation is still going.',
    points: ['Sub-second response time', 'Custom brand voice', 'Embeddable in web & mobile'],
    visual: 'voice',
  },
  {
    id: 'workflow',
    no: '05',
    title: 'Custom Agent Workflows',
    tag: 'Automation · Integrations · Ops',
    desc: 'Multi-step AI agents built around your operations. They read emails, update sheets and CRMs, generate documents and trigger actions across your tools without manual work.',
    points: ['Connects to 300+ tools & APIs', 'Approvals & guardrails built in', 'Dashboards to track every run'],
    visual: 'workflow',
  },
]

export const CALL_SCRIPT = [
  { who: 'caller', text: 'Hi, I wanted to reschedule my appointment for tomorrow.' },
  { who: 'agent', text: 'Sure! I can see your booking at 11:00 AM. Would 4:30 PM tomorrow work instead?' },
  { who: 'caller', text: 'Yes, 4:30 is perfect.' },
  { who: 'agent', text: "Done. You're booked for 4:30 PM, and I've sent the confirmation on WhatsApp." },
  { who: 'system', text: 'CRM updated · Calendar synced · WhatsApp sent' },
]

export const PROCESS = [
  { no: '01', title: 'Discover', desc: 'We map your conversations, tools and the tasks that eat up your team’s time.' },
  { no: '02', title: 'Design', desc: 'We script the agent’s persona, flows, guardrails and handoff rules together with you.' },
  { no: '03', title: 'Build & Integrate', desc: 'We train on your data and connect your CRM, helpdesk, telephony and calendars.' },
  { no: '04', title: 'Launch & Improve', desc: 'We go live, monitor every conversation and keep tuning for higher resolution rates.' },
]

// Illustrative figures; replace with real numbers from client deployments.
export const STATS = [
  { value: 24, suffix: '/7', label: 'Always-on availability' },
  { value: 70, suffix: '%', label: 'Routine queries automated' },
  { value: 3, suffix: 'x', label: 'Faster first response' },
  { value: 40, suffix: '+', label: 'Languages supported' },
]

export const INTEGRATIONS = [
  'WhatsApp', 'Twilio', 'HubSpot', 'Salesforce', 'Zendesk', 'Freshdesk', 'Shopify', 'Slack',
  'Google Sheets', 'Calendly', 'Zoho CRM', 'Exotel', 'Intercom', 'Notion', 'Stripe', 'Razorpay',
]

export const TESTIMONIALS = [
  { quote: 'Working with Devliqly was seamless. Their AI and automation solutions saved us time and increased conversions!', name: 'Vikram Singh', role: 'Digital Marketer' },
  { quote: 'Devliqly transformed our vision into a stunning digital product. Their expertise in web development and AI is unmatched!', name: 'Aarav Mehta', role: 'Startup Founder' },
  { quote: 'Our sales skyrocketed after Devliqly optimized our website and ad campaigns. Highly recommend their services!', name: 'Priya Sharma', role: 'E-commerce Owner' },
  { quote: 'Their branding and web design gave our company a fresh, modern look. Professional, creative, and efficient!', name: 'Rohan Verma', role: 'Business Consultant' },
  { quote: 'From concept to execution, Devliqly delivered beyond expectations. Their SEO and Google optimization boosted our online presence!', name: 'Ananya Iyer', role: 'SaaS Entrepreneur' },
]

export const FAQS = [
  { q: 'How long does it take to launch an AI agent?', a: 'A chatbot or support agent typically goes live in 1–2 weeks. Call and voice agents with telephony and CRM integrations usually take 2–4 weeks, depending on complexity.' },
  { q: 'Will the agent sound robotic?', a: 'No. We use state-of-the-art speech models with natural pacing and interruption handling, and you can choose or clone a custom brand voice.' },
  { q: 'Can it speak Hindi and other Indian languages?', a: 'Yes. Our agents handle English, Hindi, Hinglish and major regional languages, and they can switch mid-conversation.' },
  { q: 'What happens when the AI can’t answer?', a: 'You define the handoff rules. The agent transfers the chat or call to a human with a full summary, so the customer never has to repeat themselves.' },
  { q: 'Is my customer data secure?', a: 'Data is encrypted in transit and at rest, access is role-based, and we can deploy within your preferred region or cloud.' },
]

export const CONTACT = {
  phone: '+91-7827626940',
  email: 'contact.devliqly@gmail.com',
}
