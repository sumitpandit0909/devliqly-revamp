# Devliqly: AI Agents Website

Marketing site for [Devliqly](https://www.devliqly.in), an AI agent studio offering chatbot integration, customer service agents, inbound & outbound call agents, voice agents and custom agent workflows.

Built with React + Vite, GSAP ScrollTrigger and Lenis smooth scrolling.

## Development

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build in dist/
```

## Where things live

- `src/data.js`: all copy (services, process, stats, testimonials, FAQ, contact)
- `src/components/`: one component per section
- `src/index.css`: styles; the colour palette is set by the tokens at the top (`--accent-rgb`, `--accent-2-rgb`)
- `src/components/HeroField.jsx`: interactive dot-field background in the hero

## Blog (Strapi)

Blog posts are managed in the Strapi app in `cms/` (local only for now, SQLite database).

```bash
cd cms
cp .env.example .env   # first time only, then replace the "tobemodified" secrets
npm install
npm run seed           # optional: adds a starter post when the blog is empty
npm run develop        # admin at http://localhost:1337/admin
```

The site shows the blog (`/blog`, `/blog/<slug>`, plus Blog links in the nav and footer) only when `VITE_STRAPI_URL` is set, e.g. in `.env.development.local`:

```
VITE_STRAPI_URL=http://localhost:1337
```

Production does not set it, so devliqly.in has no blog until Strapi is hosted. To go live: deploy `cms/` (with Postgres and an upload provider), set `VITE_STRAPI_URL` in the Vercel project, and add the posts to `public/sitemap.xml`.
