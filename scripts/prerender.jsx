// Runs after `vite build`: writes a real HTML file per route (meta tags, structured data and readable content)
// plus sitemap.xml and the blog RSS feed. Built with `vite build --ssr` so it shares the app's data and helpers.
import fs from 'node:fs'
import path from 'node:path'
import { renderToStaticMarkup } from 'react-dom/server'
import { SERVICES } from '../src/data'
import { SERVICE_DETAILS } from '../src/serviceDetails'
import { LEGAL } from '../src/legal'
import { BLOG_ENABLED, STRAPI_URL, fetchAllArticles, formatDate, readTime, relatedTo } from '../src/lib/blog'
import { SITE_URL, articleMeta, blogMeta, headTags, homeMeta, legalMeta, notFoundMeta, serviceMeta } from '../src/lib/seo'
import Blocks from '../src/components/Blocks'

const DIST = path.resolve('dist')
const template = fs.readFileSync(path.join(DIST, 'index.html'), 'utf8')
  .replace(/\s*<title>[\s\S]*?<\/title>/, '')
  .replace(/\s*<meta name="description"[^>]*>/, '')

const json = (data) => JSON.stringify(data).replace(/</g, '\\u003c')

function page(meta, body, data) {
  const head = `    ${headTags(meta)}\n    <noscript><style>.prerendered{visibility:visible}</style></noscript>\n  </head>`
  const root = `<div id="root"><div class="prerendered">${renderToStaticMarkup(body)}</div></div>${data ? `\n    <script id="page-data" type="application/json">${json(data)}</script>` : ''}`
  return template.replace(/\s*<\/head>/, `\n${head}`).replace('<div id="root"></div>', root)
}

// cleanUrls on Vercel serves /privacy from privacy.html
function write(route, html) {
  const file = route === '/' ? 'index.html' : `${route.slice(1)}.html`
  const out = path.join(DIST, file)
  fs.mkdirSync(path.dirname(out), { recursive: true })
  fs.writeFileSync(out, html)
}

const SiteLinks = () => (
  <nav aria-label="Site">
    <ul>
      <li><a href="/">Home</a></li>
      {SERVICES.map((s) => <li key={s.id}><a href={`/services/${s.slug}`}>{s.title}</a></li>)}
      {BLOG_ENABLED && <li><a href="/blog">Blog</a></li>}
      <li><a href="/privacy">Privacy Policy</a></li>
      <li><a href="/terms">Terms &amp; Conditions</a></li>
    </ul>
  </nav>
)

const Shell = ({ children }) => (
  <>
    <header><a href="/">Devliqly</a><SiteLinks /></header>
    <main>{children}</main>
  </>
)

const Faqs = ({ items }) => (
  <section>
    <h2>Frequently asked questions</h2>
    <dl>{items.map((f) => <div key={f.q}><dt>{f.q}</dt><dd>{f.a}</dd></div>)}</dl>
  </section>
)

const List = ({ title, items }) => (
  <section>
    <h2>{title}</h2>
    <ul>{items.map((x) => <li key={x.title}><h3>{x.title}</h3><p>{x.desc}</p></li>)}</ul>
  </section>
)

const Teaser = ({ a }) => (
  <article>
    <h2><a href={`/blog/${a.slug}`}>{a.title}</a></h2>
    <p><time dateTime={a.publishedAt}>{formatDate(a.publishedAt)}</time> · {a.category}</p>
    <p>{a.excerpt}</p>
  </article>
)

// The CMS sleeps when idle on Render's free tier, so give it time to wake before giving up
const ATTEMPTS = 5
const RETRY_DELAY_MS = 15000

async function loadArticles() {
  if (!BLOG_ENABLED) return null
  for (let attempt = 1; ; attempt++) {
    try {
      return await fetchAllArticles()
    } catch (err) {
      if (attempt === ATTEMPTS) {
        // A CMS outage should not take the whole site down: ship it without pre-rendered posts
        console.warn(`prerender: could not load posts from ${STRAPI_URL} (${err.message}); skipping blog pages`)
        return null
      }
      console.warn(`prerender: CMS not ready (${err.message}), retrying in ${RETRY_DELAY_MS / 1000}s`)
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS))
    }
  }
}

// List entries don't need the full post body
function teaser(article) {
  const copy = { ...article }
  delete copy.content
  return copy
}

const xml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

async function main() {
  const routes = []
  const add = (route, meta, body, data) => {
    write(route, page(meta, <Shell>{body}</Shell>, data))
    routes.push(route)
  }

  const home = homeMeta()
  add('/', home, <><h1>AI agents that work for you</h1><p>{home.description}</p></>)

  for (const s of SERVICES) {
    const d = SERVICE_DETAILS[s.id]
    add(`/services/${s.slug}`, serviceMeta(s, d), (
      <>
        <h1>{s.title}</h1>
        <p>{d.intro}</p>
        <ul>{s.points.map((p) => <li key={p}>{p}</li>)}</ul>
        <List title="What you get" items={d.features} />
        <List title="Use cases" items={d.useCases} />
        <List title="How we build it" items={d.steps} />
        <Faqs items={d.faqs} />
      </>
    ))
  }

  for (const doc of Object.values(LEGAL)) {
    add(doc.path, legalMeta(doc), (
      <>
        <h1>{doc.title}</h1>
        <p>Last updated: {doc.updated}</p>
        <p>{doc.intro}</p>
        {doc.sections.map((sec) => (
          <section key={sec.h}>
            <h2>{sec.h}</h2>
            {sec.body.map((b, i) => (Array.isArray(b) ? <ul key={i}>{b.map((li) => <li key={li}>{li}</li>)}</ul> : <p key={i}>{b}</p>))}
          </section>
        ))}
      </>
    ))
  }

  const articles = await loadArticles()
  if (articles) {
    const blog = blogMeta(articles)
    add('/blog', blog, (
      <>
        <h1>Blog</h1>
        <p>{blog.description}</p>
        {articles.map((a) => <Teaser a={a} key={a.documentId} />)}
      </>
    ), { kind: 'blog', key: '/blog', articles: articles.map(teaser) })

    for (const a of articles) {
      const related = relatedTo(a, articles).map(teaser)
      add(`/blog/${a.slug}`, articleMeta(a), (
        <article>
          <h1>{a.title}</h1>
          <p>{a.author || 'Team Devliqly'} · <time dateTime={a.publishedAt}>{formatDate(a.publishedAt)}</time> · {readTime(a.content)}</p>
          <p>{a.excerpt}</p>
          <Blocks content={a.content} />
          {related.length > 0 && <aside><h2>Keep reading</h2>{related.map((r) => <Teaser a={r} key={r.documentId} />)}</aside>}
        </article>
      ), { kind: 'post', key: a.slug, article: a, related })
    }


    const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Devliqly Blog</title>
    <link>${SITE_URL}/blog</link>
    <description>${xml(blog.description)}</description>
    <language>en-in</language>
    <atom:link href="${SITE_URL}/blog/rss.xml" rel="self" type="application/rss+xml" />
${articles.map((a) => `    <item>
      <title>${xml(a.title)}</title>
      <link>${SITE_URL}/blog/${a.slug}</link>
      <guid isPermaLink="true">${SITE_URL}/blog/${a.slug}</guid>
      <pubDate>${new Date(a.publishedAt).toUTCString()}</pubDate>
      <category>${xml(a.category)}</category>
      <description>${xml(a.excerpt)}</description>
    </item>`).join('\n')}
  </channel>
</rss>
`
    fs.writeFileSync(path.join(DIST, 'blog', 'rss.xml'), rss)
  }

  if (BLOG_ENABLED) {
    const blog = blogMeta(articles ?? [])
    // Without posts (CMS down during the build) the blog page loads them in the browser instead
    if (!articles) write('/blog', page({ ...blog, rss: false }, <Shell><h1>Blog</h1><p>{blog.description}</p></Shell>))
    // Posts published after this build are served this shell until the CMS triggers the next deploy
    write('/blog/post-shell', page({ title: 'Blog | DEVLIQLY', description: blog.description, rss: Boolean(articles) }, <Shell><p>Loading post…</p></Shell>))
  }

  write('/404', page(notFoundMeta(), <Shell><h1>Page not found</h1><p>The page you’re looking for doesn’t exist or has moved.</p></Shell>))

  // Only blog pages carry a real modified date; a build date would change on every deploy and mislead crawlers
  const lastmod = Object.fromEntries((articles ?? []).map((a) => [`/blog/${a.slug}`, (a.updatedAt || a.publishedAt).slice(0, 10)]))
  if (articles?.length) lastmod['/blog'] = Object.values(lastmod).sort().pop()
  const priority = (r) => (r === '/' ? '1.0' : r.startsWith('/services/') ? '0.8' : r.startsWith('/blog') ? '0.7' : '0.3')
  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${routes.map((r) => `  <url>
    <loc>${SITE_URL}${r === '/' ? '/' : r}</loc>
${lastmod[r] ? `    <lastmod>${lastmod[r]}</lastmod>
` : ''}    <priority>${priority(r)}</priority>
  </url>`).join('\n')}
</urlset>
`
  fs.writeFileSync(path.join(DIST, 'sitemap.xml'), sitemap)
  console.log(`prerender: ${routes.length} pages${articles ? ` (${articles.length} posts)` : ', blog off'}, sitemap.xml${articles ? ', blog/rss.xml' : ''}`)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
