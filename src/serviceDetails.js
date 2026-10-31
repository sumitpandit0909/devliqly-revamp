// Long-form content for each service page, keyed by SERVICES[].id
export const SERVICE_DETAILS = {
  chatbot: {
    headline: ['Chatbots that', 'actually', 'help'],
    intro: 'We build AI chatbots that know your products, policies and prices, and put them wherever your customers already message you. They answer instantly, qualify leads and book appointments, then pass warm conversations to your team.',
    features: [
      { title: 'Trained on your business', desc: 'We feed the bot your website, catalogue, FAQs and policy documents so its answers are specific to you, not generic.' },
      { title: 'Every channel, one brain', desc: 'One assistant across your website, WhatsApp, Instagram and Facebook Messenger, with the same knowledge and tone everywhere.' },
      { title: 'Lead capture built in', desc: 'It asks the right qualifying questions and pushes name, number and intent straight into your CRM or a Google Sheet.' },
      { title: 'Bookings and orders', desc: 'Customers can book slots, check order status or get a quote without leaving the chat.' },
      { title: 'Speaks your customers’ language', desc: 'English, Hindi, Hinglish and major regional languages, switching automatically to match the customer.' },
      { title: 'Human handoff', desc: 'When a question needs a person, the chat moves to your team with the full conversation attached.' },
    ],
    useCases: [
      { title: 'E-commerce', desc: 'Product questions, delivery checks, order tracking and abandoned-cart nudges on WhatsApp.' },
      { title: 'Clinics & salons', desc: 'Appointment booking, rescheduling and reminders, around the clock.' },
      { title: 'Real estate', desc: 'Qualify buyers by budget and location, then schedule site visits.' },
      { title: 'Education', desc: 'Course enquiries, fee details and counselling call bookings for admissions teams.' },
    ],
    steps: [
      { title: 'Collect knowledge', desc: 'We gather your docs, FAQs and past chats and turn them into the bot’s knowledge base.' },
      { title: 'Design conversations', desc: 'We script greetings, lead questions, tone and the rules for when to hand off to a human.' },
      { title: 'Connect channels', desc: 'We install the widget on your site and connect WhatsApp Business, Instagram and Messenger.' },
      { title: 'Launch and tune', desc: 'We review real conversations every week and improve answers that missed the mark.' },
    ],
    tools: ['WhatsApp Business', 'Instagram', 'Messenger', 'Website widget', 'HubSpot', 'Zoho CRM', 'Google Sheets', 'Calendly', 'Shopify'],
    faqs: [
      { q: 'Do I need a WhatsApp Business API account?', a: 'For WhatsApp, yes. We help you set it up through an official provider, including number verification and message templates.' },
      { q: 'What if the bot gives a wrong answer?', a: 'It answers only from the knowledge you approve and says so when it is unsure. You can review every conversation and we correct gaps quickly.' },
      { q: 'Can I edit what the bot knows myself?', a: 'Yes. You get a simple way to update FAQs, prices and documents, and changes go live without a rebuild.' },
    ],
  },

  support: {
    headline: ['Support that', 'never', 'sleeps'],
    intro: 'Our customer service agent works inside your helpdesk and resolves the repetitive tickets on its own: order status, refunds, returns, account changes and troubleshooting. Your team spends its time on the cases that genuinely need a human.',
    features: [
      { title: 'Resolves, not just replies', desc: 'Connected to your order, billing and account systems, the agent can look things up and take action, not only answer questions.' },
      { title: 'Works in your helpdesk', desc: 'Runs inside Zendesk, Freshdesk, Intercom or your own system, so your team keeps its existing workflow.' },
      { title: 'Policy-aware', desc: 'Follows your refund, return and escalation rules exactly, with approval steps where you want them.' },
      { title: 'Smart escalation', desc: 'Detects frustration, VIP customers or sensitive topics and routes them to the right person with a summary.' },
      { title: 'Consistent tone', desc: 'Every reply matches your brand voice, in the customer’s language, at any hour.' },
      { title: 'Clear reporting', desc: 'See resolution rates, top topics and handoff reasons so you know what to fix upstream.' },
    ],
    useCases: [
      { title: 'D2C brands', desc: 'Where-is-my-order, returns, exchanges and refund status, resolved end to end.' },
      { title: 'SaaS', desc: 'Password resets, plan changes, billing questions and first-line troubleshooting.' },
      { title: 'Fintech & insurance', desc: 'Policy and account queries with strict guardrails and audit trails.' },
      { title: 'Travel & hospitality', desc: 'Booking changes, cancellations and pre-trip questions during peak season.' },
    ],
    steps: [
      { title: 'Audit tickets', desc: 'We analyse past tickets to find the topics that are high-volume and safe to automate.' },
      { title: 'Connect systems', desc: 'We integrate your helpdesk plus the order, CRM or billing tools the agent needs to take action.' },
      { title: 'Set guardrails', desc: 'Together we define what the agent may do alone, what needs approval and what always goes to a human.' },
      { title: 'Roll out gradually', desc: 'We start with a few topics, measure accuracy, then expand coverage as confidence grows.' },
    ],
    tools: ['Zendesk', 'Freshdesk', 'Intercom', 'Gorgias', 'Shopify', 'Razorpay', 'Stripe', 'Salesforce', 'Slack'],
    faqs: [
      { q: 'Will it replace my support team?', a: 'No. It takes the repetitive load off them. Most teams use the freed-up time for complex cases, proactive outreach and quality.' },
      { q: 'Can it issue refunds by itself?', a: 'Only if you allow it. You can set limits, for example automatic refunds below a certain amount and approval above it.' },
      { q: 'How do customers reach a human?', a: 'They can ask at any time, and the agent also escalates on its own based on the rules you set.' },
    ],
  },

  calls: {
    headline: ['Every call', 'answered.', 'Every lead called.'],
    intro: 'Inbound agents pick up every call on the first ring, answer questions, book appointments and route callers. Outbound agents run your follow-ups, reminders, surveys and collection calls at scale, with natural conversation instead of a robotic IVR.',
    features: [
      { title: 'Unlimited concurrency', desc: 'Handle a spike of hundreds of simultaneous calls without hold music or missed leads.' },
      { title: 'Natural conversation', desc: 'Callers speak normally and can interrupt; no “press 1 for sales” menus.' },
      { title: 'Outbound campaigns', desc: 'Upload a list or trigger calls from your CRM for lead follow-up, payment reminders, feedback and renewals.' },
      { title: 'Live transfer', desc: 'Hot leads and complex callers are transferred to the right person, with context whispered or shared.' },
      { title: 'Recordings & transcripts', desc: 'Every call is recorded, transcribed, summarised and tagged with outcome and sentiment.' },
      { title: 'Your existing numbers', desc: 'Works with your current telephony provider or new local numbers through Exotel, Twilio and others.' },
    ],
    useCases: [
      { title: 'Lead follow-up', desc: 'Call new leads within a minute of a form fill, qualify them and book a meeting.' },
      { title: 'Appointment reminders', desc: 'Confirm, reschedule or cancel bookings to cut no-shows.' },
      { title: 'Collections', desc: 'Polite, compliant payment reminders with payment links sent by SMS or WhatsApp.' },
      { title: 'Front desk overflow', desc: 'Answer after-hours and overflow calls so no customer reaches voicemail.' },
    ],
    steps: [
      { title: 'Map call flows', desc: 'We document why people call you, or why you call them, and what a good outcome looks like.' },
      { title: 'Script & voice', desc: 'We write the agent’s script and choose a voice and language mix that fits your brand.' },
      { title: 'Connect telephony', desc: 'We connect your numbers, CRM and calendar, and set transfer and compliance rules.' },
      { title: 'Test and go live', desc: 'We run test calls with your team, launch, and keep reviewing recordings to improve.' },
    ],
    tools: ['Exotel', 'Twilio', 'Knowlarity', 'Plivo', 'HubSpot', 'Salesforce', 'Zoho CRM', 'Google Calendar', 'WhatsApp'],
    faqs: [
      { q: 'Can callers tell it’s an AI?', a: 'The voice is natural, but we recommend the agent introduces itself as an AI assistant. It builds trust and helps with compliance.' },
      { q: 'Is outbound calling compliant with Indian regulations?', a: 'We build in consent checks, calling-hour limits and DND handling. You remain responsible for having consent to contact the numbers you upload.' },
      { q: 'What does it cost per call?', a: 'Pricing depends on call volume, duration and telephony provider. We share a clear per-minute estimate after the discovery call.' },
    ],
  },

  voice: {
    headline: ['A voice for', 'your', 'product'],
    intro: 'We build real-time voice agents you can embed in your app, website or kiosk. They listen, think and respond in under a second, handle interruptions naturally, and take actions in your systems while the conversation is still going.',
    features: [
      { title: 'Sub-second latency', desc: 'Streaming speech recognition and synthesis keep the conversation flowing without awkward pauses.' },
      { title: 'Interruptions handled', desc: 'Users can cut in, change their mind or correct themselves, just like talking to a person.' },
      { title: 'Custom brand voice', desc: 'Pick from premium voices or create a custom voice that is unique to your brand.' },
      { title: 'Actions mid-conversation', desc: 'The agent can search inventory, fill forms or book slots through your APIs while it talks.' },
      { title: 'Web, mobile & kiosk', desc: 'SDKs and embeds for browsers, iOS, Android and in-store hardware.' },
      { title: 'Multilingual', desc: 'Converse in English, Hindi and regional languages, including mixed-language speech.' },
    ],
    useCases: [
      { title: 'In-app assistants', desc: 'Let users navigate, search and complete tasks in your app by speaking.' },
      { title: 'Kiosks & retail', desc: 'Voice help desks for stores, hospitals, hotels and events.' },
      { title: 'Training & coaching', desc: 'Role-play partners for sales training, interviews and language practice.' },
      { title: 'Accessibility', desc: 'Hands-free and screen-free access for users who prefer or need voice.' },
    ],
    steps: [
      { title: 'Define the experience', desc: 'We agree what the agent should know, do and sound like, and where it will live.' },
      { title: 'Build the brain', desc: 'We connect the language model to your knowledge and the APIs it needs to take action.' },
      { title: 'Tune the voice', desc: 'We tune voice, pacing, turn-taking and latency on real devices and networks.' },
      { title: 'Embed and ship', desc: 'We hand over the SDK integration or embed it for you, then monitor quality after launch.' },
    ],
    tools: ['Web SDK', 'iOS', 'Android', 'React Native', 'REST APIs', 'Webhooks', 'Google Sheets', 'Notion', 'Slack'],
    faqs: [
      { q: 'How is this different from a call agent?', a: 'Call agents run over phone lines. Voice agents are embedded directly in your own app, website or device, often with a visual interface alongside.' },
      { q: 'Can you clone a specific person’s voice?', a: 'Only with that person’s documented consent. We can also design an original voice for your brand.' },
      { q: 'Does it work on slow networks?', a: 'We optimise for Indian mobile networks and degrade gracefully, but a stable connection gives the best experience.' },
    ],
  },

  workflow: {
    headline: ['Let agents', 'run the', 'busywork'],
    intro: 'Custom agent workflows take over the multi-step, repetitive work that keeps your team busy: reading emails, updating sheets and CRMs, preparing documents and following up. Each workflow has clear guardrails, approvals where you need them, and a log of every run.',
    features: [
      { title: 'Built around your process', desc: 'We model the workflow you already run, step by step, instead of forcing a generic template.' },
      { title: 'Connects everything', desc: 'Email, Sheets, CRMs, ERPs, accounting tools and internal APIs, linked into one flow.' },
      { title: 'Understands documents', desc: 'Reads invoices, purchase orders, resumes and forms, and extracts the fields you need.' },
      { title: 'Human approvals', desc: 'Add review steps for anything sensitive, approved in one click from Slack, email or WhatsApp.' },
      { title: 'Runs on schedule or trigger', desc: 'Start workflows on a timer, a new email, a form submission or an event in any connected tool.' },
      { title: 'Full visibility', desc: 'A dashboard shows every run, its inputs, outputs and any errors, so nothing happens silently.' },
    ],
    useCases: [
      { title: 'Sales ops', desc: 'Enrich new leads, update the CRM, draft follow-up emails and alert the right rep.' },
      { title: 'Finance', desc: 'Extract invoice data, match it to purchase orders and prepare entries for approval.' },
      { title: 'Hiring', desc: 'Screen resumes against a role, schedule interviews and keep candidates updated.' },
      { title: 'Reporting', desc: 'Pull data from several tools and send a written weekly summary to stakeholders.' },
    ],
    steps: [
      { title: 'Shadow the process', desc: 'We walk through the task with the people who do it today and note every step and exception.' },
      { title: 'Design the agent', desc: 'We decide which steps are automated, which need approval and how errors are handled.' },
      { title: 'Build & integrate', desc: 'We connect your tools, build the workflow and test it on real historical data.' },
      { title: 'Operate & extend', desc: 'We monitor runs, fix edge cases and add new workflows as you find more to automate.' },
    ],
    tools: ['Gmail', 'Outlook', 'Google Sheets', 'Notion', 'Slack', 'HubSpot', 'Zoho', 'Tally', 'Custom APIs'],
    faqs: [
      { q: 'How is this different from Zapier or Make?', a: 'Those tools move data between apps. Our agents also read, decide and write, handling unstructured inputs like emails and documents that rule-based automations can’t.' },
      { q: 'What if a workflow makes a mistake?', a: 'Sensitive steps go through human approval, every run is logged, and errors alert your team instead of failing silently.' },
      { q: 'Who owns the workflows?', a: 'You do. We document every workflow and can run it in your own cloud account if you prefer.' },
    ],
  },
}
