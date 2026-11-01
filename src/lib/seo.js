import { CONTACT, FAQS } from '../data'
import { coverImage } from './blog'

// Page metadata shared by the browser (on navigation) and the build-time prerender (in the HTML Google and link previews read)
export const SITE_URL = 'https://www.devliqly.in'
export const SITE_NAME = 'Devliqly'
const DEFAULT_IMAGE = `${SITE_URL}/og-image.png`
const RSS_URL = `${SITE_URL}/blog/rss.xml`

const ORG = {
  '@type': 'Organization',
  '@id': `${SITE_URL}/#org`,
  name: SITE_NAME,
  url: SITE_URL,
  logo: `${SITE_URL}/logo.png`,
  email: CONTACT.email,
  telephone: CONTACT.phone,
}

const clip = (text = '', max = 160) => (text.length <= max ? text : `${text.slice(0, max - 1).replace(/\s+\S*$/, '')}…`)

const faqPage = (faqs) => ({
  '@type': 'FAQPage',
  mainEntity: faqs.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
})

const crumbs = (items) => ({
  '@type': 'BreadcrumbList',
  itemListElement: items.map(([name, path], i) => ({ '@type': 'ListItem', position: i + 1, name, item: SITE_URL + path })),
})

export const homeMeta = () => ({
  title: 'DEVLIQLY | AI Agents That Work For You',
  description: 'Devliqly builds AI agents that talk, listen and work for your business: chatbot integration, customer service agents, inbound and outbound call agents, voice agents and custom agent workflows.',
  path: '/',
  jsonLd: [ORG, { '@type': 'WebSite', name: SITE_NAME, url: SITE_URL, publisher: { '@id': ORG['@id'] } }, faqPage(FAQS)],
})

export const serviceMeta = (service, details) => ({
  title: `${service.title} | DEVLIQLY`,
  description: clip(details.intro),
  path: `/services/${service.slug}`,
  jsonLd: [
    { '@type': 'Service', name: service.title, description: details.intro, serviceType: service.title, provider: ORG, areaServed: 'Worldwide', url: `${SITE_URL}/services/${service.slug}` },
    crumbs([['Home', '/'], ['Services', '/#services'], [service.title, `/services/${service.slug}`]]),
    faqPage(details.faqs),
  ],
})

export const legalMeta = (doc) => ({
  title: `${doc.title} | DEVLIQLY`,
  description: clip(doc.intro),
  path: doc.path,
})

export const blogMeta = (articles = []) => ({
  title: 'Blog | DEVLIQLY',
  description: 'Field notes from Devliqly on AI agents, chatbots, voice agents and automation for growing businesses.',
  path: '/blog',
  rss: true,
  jsonLd: [
    {
      '@type': 'Blog',
      name: 'Devliqly Blog',
      url: `${SITE_URL}/blog`,
      publisher: ORG,
      blogPost: articles.slice(0, 20).map((a) => ({ '@type': 'BlogPosting', headline: a.title, url: `${SITE_URL}/blog/${a.slug}`, datePublished: a.publishedAt })),
    },
    crumbs([['Home', '/'], ['Blog', '/blog']]),
  ],
})

export function articleMeta(a) {
  const path = `/blog/${a.slug}`
  const image = coverImage(a.cover, 'large')?.src
  return {
    title: `${a.seoTitle || a.title} | DEVLIQLY`,
    description: clip(a.seoDescription || a.excerpt),
    path,
    image,
    type: 'article',
    rss: true,
    article: { published: a.publishedAt, modified: a.updatedAt, section: a.category },
    jsonLd: [
      {
        '@type': 'BlogPosting',
        headline: a.title,
        description: a.seoDescription || a.excerpt,
        image: image ? [image] : [DEFAULT_IMAGE],
        datePublished: a.publishedAt,
        dateModified: a.updatedAt || a.publishedAt,
        articleSection: a.category,
        author: { '@type': 'Organization', name: a.author || SITE_NAME, url: SITE_URL },
        publisher: ORG,
        mainEntityOfPage: { '@type': 'WebPage', '@id': SITE_URL + path },
      },
      crumbs([['Home', '/'], ['Blog', '/blog'], [a.title, path]]),
    ],
  }
}

export const notFoundMeta = () => ({ title: 'Page not found | DEVLIQLY', noindex: true })

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

// Every tag this module manages, as [tagName, attributes]
function tagList(meta) {
  const url = meta.path ? SITE_URL + meta.path : null
  const image = meta.image || DEFAULT_IMAGE
  const tags = [
    ['meta', { name: 'description', content: meta.description }],
    ['meta', { name: 'robots', content: meta.noindex ? 'noindex, follow' : 'index, follow, max-image-preview:large' }],
    ['link', { rel: 'canonical', href: url }],
    ['meta', { property: 'og:site_name', content: SITE_NAME }],
    ['meta', { property: 'og:locale', content: 'en_IN' }],
    ['meta', { property: 'og:type', content: meta.type || 'website' }],
    ['meta', { property: 'og:title', content: meta.title }],
    ['meta', { property: 'og:description', content: meta.description }],
    ['meta', { property: 'og:url', content: url }],
    ['meta', { property: 'og:image', content: image }],
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { name: 'twitter:title', content: meta.title }],
    ['meta', { name: 'twitter:description', content: meta.description }],
    ['meta', { name: 'twitter:image', content: image }],
    ['meta', { property: 'article:published_time', content: meta.article?.published }],
    ['meta', { property: 'article:modified_time', content: meta.article?.modified }],
    ['meta', { property: 'article:section', content: meta.article?.section }],
    ['link', { rel: 'alternate', type: 'application/rss+xml', title: 'Devliqly Blog', href: meta.rss ? RSS_URL : null }],
  ]
  // Skip tags whose value is missing
  return tags.filter(([, attrs]) => attrs.content ?? attrs.href)
}

const jsonLdText = (meta) =>
  meta.jsonLd ? JSON.stringify({ '@context': 'https://schema.org', '@graph': meta.jsonLd }).replace(/</g, '\\u003c') : null

// HTML for the <head>, used by the prerender
export function headTags(meta) {
  const tags = tagList(meta).map(([tag, attrs]) => `<${tag} data-seo ${Object.entries(attrs).map(([k, v]) => `${k}="${esc(v)}"`).join(' ')} />`)
  const ld = jsonLdText(meta)
  if (ld) tags.push(`<script data-seo type="application/ld+json">${ld}</script>`)
  return `<title>${esc(meta.title)}</title>\n    ${tags.join('\n    ')}`
}

// Swaps the managed tags in the live document after a client-side navigation
export function applyMeta(meta) {
  document.title = meta.title
  document.head.querySelectorAll('[data-seo], meta[name="description"]').forEach((el) => el.remove())
  const frag = document.createDocumentFragment()
  for (const [tag, attrs] of tagList(meta)) {
    const el = document.createElement(tag)
    el.setAttribute('data-seo', '')
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v))
    frag.append(el)
  }
  const ld = jsonLdText(meta)
  if (ld) {
    const script = document.createElement('script')
    script.type = 'application/ld+json'
    script.setAttribute('data-seo', '')
    script.textContent = ld
    frag.append(script)
  }
  document.head.append(frag)
}
