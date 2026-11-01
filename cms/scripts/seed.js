'use strict';

// Adds the starter articles that are missing (matched by slug). Run with: npm run seed
const { createStrapi, compileStrapi } = require('@strapi/strapi');

const text = (t) => ({ type: 'text', text: t });
const p = (t) => ({ type: 'paragraph', children: [text(t)] });
const h = (level, t) => ({ type: 'heading', level, children: [text(t)] });
const list = (items) => ({
  type: 'list',
  format: 'unordered',
  children: items.map((t) => ({ type: 'list-item', children: [text(t)] })),
});

const STARTERS = [
  {
  title: 'Where AI agents actually pay off for small businesses',
  slug: 'where-ai-agents-pay-off',
  excerpt: 'Not every task needs an agent. Here are the four places we see AI agents earn their keep fastest, and how to spot them in your own business.',
  category: 'AI Agents',
  author: 'Team Devliqly',
  content: [
    p('Most teams we talk to want “AI” somewhere, but the wins come from picking the right job for it. These are the four places we see agents pay off fastest.'),
    h(2, '1. Questions you answer every single day'),
    p('If your team copies the same answers into WhatsApp and email, a chatbot trained on your docs can handle most of them instantly and hand the rest to a person.'),
    h(2, '2. Calls you miss after hours'),
    p('A voice agent can pick up, qualify the caller and book the appointment while you sleep, then drop a summary in your inbox.'),
    h(2, '3. Follow-ups that slip through the cracks'),
    list(['Payment reminders', 'Appointment confirmations', 'Lead nurturing after a demo']),
    h(2, '4. Busywork between your tools'),
    p('Copying leads from forms to a CRM or invoices to a sheet is exactly the kind of work a custom agent workflow can take over.'),
    { type: 'quote', children: [text('Start with one repetitive task, measure it, then expand.')] },
    p('Want to see which of these fits your business? Book a free demo and we will map it out with you.'),
  ],
  featured: true,
  },
  {
    title: 'Chatbot vs voice agent: which one should you launch first?',
    slug: 'chatbot-vs-voice-agent',
    excerpt: 'Both answer customers around the clock, but they shine in different places. A quick guide to choosing your first AI agent.',
    category: 'Chatbots',
    author: 'Team Devliqly',
    content: [
      p('If you are adding AI to customer conversations for the first time, the usual question is where to start: a chatbot on your website and WhatsApp, or a voice agent on your phone line.'),
      h(2, 'Start with a chatbot when'),
      list(['Most enquiries arrive on your website, Instagram or WhatsApp', 'Answers involve links, prices or documents', 'You want the fastest launch, usually one to two weeks']),
      h(2, 'Start with a voice agent when'),
      list(['Your phone rings more than your inbox', 'Callers need bookings, confirmations or order status', 'Missed calls are costing you leads after hours']),
      h(2, 'What both need'),
      p('Either way, the agent is only as good as what it knows. We start by collecting your FAQs, policies and pricing, then decide which questions should go to a person.'),
      h(3, 'A simple rule of thumb'),
      p('Count last month’s conversations by channel. Launch where the volume is, then add the second channel using the same knowledge base.'),
    ],
  },
  {
    title: 'Five automations that save a growing team ten hours a week',
    slug: 'five-automations-save-ten-hours',
    excerpt: 'Small workflows add up. These five agent-driven automations remove the copy-paste work most teams quietly live with.',
    category: 'Automation',
    author: 'Team Devliqly',
    content: [
      p('Most of the time we save for clients comes from small, boring workflows rather than one big system. Here are the five we build most often.'),
      h(2, '1. Leads straight into the CRM'),
      p('Form fills, WhatsApp chats and calls are logged with a summary and next step, without anyone retyping them.'),
      h(2, '2. Invoices into a sheet'),
      p('An agent reads incoming invoices, extracts the totals and dates, and files them where your accountant expects them.'),
      h(2, '3. Appointment reminders'),
      p('Reminders and confirmations go out automatically, and replies such as “reschedule” are handled on the spot.'),
      h(2, '4. Daily summaries'),
      p('A short morning digest of yesterday’s enquiries, bookings and open issues lands in your inbox or Slack.'),
      h(2, '5. Review requests'),
      p('Happy customers get a polite review request at the right moment, while unhappy ones are routed to you first.'),
    ],
  },
];

async function main() {
  const app = await createStrapi(await compileStrapi()).load();
  const articles = app.documents('api::article.article');

  let added = 0;
  for (const starter of STARTERS) {
    const exists = await articles.findFirst({ filters: { slug: starter.slug } });
    if (exists) continue;
    await articles.create({ data: starter, status: 'published' });
    console.log(`Seeded "${starter.title}"`);
    added++;
  }
  if (!added) console.log('All starter articles already exist, nothing to seed');

  await app.destroy();
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
