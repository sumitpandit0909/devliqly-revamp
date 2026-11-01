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

### Hosting the CMS on blog.devliqly.in (Render + Neon + Cloudinary)

The CMS runs on Render's free tier from the `render.yaml` blueprint, with its database on Neon and images on Cloudinary. Render's free instance sleeps after 15 minutes idle: the admin takes about 30 seconds to wake, and visitors are unaffected because they read the pre-rendered pages on Vercel. The site build retries for about a minute while the CMS wakes.

1. **Neon:** create a project in region *AWS Asia Pacific (Singapore)* and copy the **direct** connection string (Connection details → turn *Connection pooling* off).
2. **Cloudinary:** create a free account and copy the cloud name, API key and API secret from the dashboard.
3. **Render:** New → Blueprint → pick this repository. Render reads `render.yaml`, generates the secrets, and asks for `DATABASE_URL`, the three `CLOUDINARY_*` values and `SITE_DEPLOY_HOOK` (leave this empty for now). The first deploy creates the tables in Neon.
4. **Domain:** in the Render service → Settings → Custom Domains, add `blog.devliqly.in`. In Cloudflare DNS add the CNAME it shows (`blog` → `devliqly-cms.onrender.com`) with the proxy **off** (grey cloud) until Render issues the certificate.
5. Open https://blog.devliqly.in/admin, create the admin account and write the post.
6. **Rebuild on publish:** in Vercel, Project → Settings → Git → Deploy Hooks, create a hook for `main`, then paste its URL as `SITE_DEPLOY_HOOK` in Render.
7. **Turn the blog on:** in Vercel add `VITE_STRAPI_URL=https://blog.devliqly.in` (Production) and redeploy.
