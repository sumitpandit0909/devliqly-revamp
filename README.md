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

Posts are written in the Strapi CMS in `cms/` (hosted at https://blog.devliqly.in) and published on the site at `/blog` and `/blog/<slug>`.

### Local development

```bash
cd cms
cp .env.example .env   # first time only, then replace the "tobemodified" secrets
npm install
npm run seed           # optional: adds the starter posts that are missing
npm run develop        # admin at http://localhost:1337/admin
```

The site only shows the blog when `VITE_STRAPI_URL` is set, e.g. in `.env.development.local`:

```
VITE_STRAPI_URL=http://localhost:1337
```

### SEO: how pages reach search engines

`npm run build` runs `vite build` and then `scripts/prerender.jsx`, which writes a real HTML file for every route (home, services, legal pages, the blog and each post) with its own title, description, canonical URL, Open Graph/Twitter tags, JSON-LD structured data and readable content. It also generates `sitemap.xml` and `blog/rss.xml` from the published posts. Posts are fetched from Strapi at build time, so publishing in Strapi triggers a Vercel rebuild (see `SITE_DEPLOY_HOOK` below). If Strapi is unreachable during a build, the site still deploys without pre-rendered blog pages.

### Hosting the CMS on blog.devliqly.in

1. Deploy `cms/` to any Node host (VPS, Railway, Render, Fly, Coolify…). A `Dockerfile` is included; without Docker run `npm ci && npm run build && npm run start`.
2. Give it a Postgres database and a persistent disk for `public/uploads` (or configure an upload provider such as S3 or Cloudinary).
3. Set the environment variables from `cms/.env.example`: fresh random secrets, `NODE_ENV=production`, `PUBLIC_URL=https://blog.devliqly.in`, `DATABASE_CLIENT=postgres`, `DATABASE_URL=...`.
4. In Cloudflare DNS, point `blog` at the host (CNAME or A record) and enable HTTPS.
5. Open https://blog.devliqly.in/admin, create the admin account and add posts.
6. In Vercel, create a Deploy Hook (Project → Settings → Git → Deploy Hooks, branch `main`) and set its URL as `SITE_DEPLOY_HOOK` on the CMS, so publishing or editing a post rebuilds the site.
7. In Vercel, add `VITE_STRAPI_URL=https://blog.devliqly.in` (Production) and redeploy. The Blog link, pages, sitemap entries and RSS feed then go live.
