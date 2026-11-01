'use strict';

// Adds a first published article when the blog is empty. Run with: npm run seed
const { createStrapi, compileStrapi } = require('@strapi/strapi');

const text = (t) => ({ type: 'text', text: t });
const p = (t) => ({ type: 'paragraph', children: [text(t)] });
const h = (level, t) => ({ type: 'heading', level, children: [text(t)] });
const list = (items) => ({
  type: 'list',
  format: 'unordered',
  children: items.map((t) => ({ type: 'list-item', children: [text(t)] })),
});

const WELCOME = {
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
};

async function main() {
  const app = await createStrapi(await compileStrapi()).load();
  const articles = app.documents('api::article.article');

  if ((await articles.count()) === 0) {
    await articles.create({ data: WELCOME, status: 'published' });
    console.log(`Seeded "${WELCOME.title}"`);
  } else {
    console.log('Articles already exist, nothing to seed');
  }

  await app.destroy();
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
