// Blog content comes from the Strapi app in /cms. Without VITE_STRAPI_URL the blog stays switched off.
export const STRAPI_URL = (import.meta.env.VITE_STRAPI_URL || '').replace(/\/+$/, '')
export const BLOG_ENABLED = Boolean(STRAPI_URL)

const LIST_QUERY = [
  'fields[0]=title', 'fields[1]=slug', 'fields[2]=excerpt', 'fields[3]=category', 'fields[4]=publishedAt',
  'fields[5]=updatedAt', 'fields[6]=author', 'fields[7]=featured',
  'populate[cover][fields][0]=url', 'populate[cover][fields][1]=alternativeText', 'populate[cover][fields][2]=width',
  'populate[cover][fields][3]=height', 'populate[cover][fields][4]=formats',
  'sort=publishedAt:desc',
].join('&')

async function get(query) {
  const res = await fetch(`${STRAPI_URL}/api/articles?${query}`)
  if (!res.ok) throw new Error(`Strapi responded ${res.status}`)
  return res.json()
}

export const fetchArticles = async () => (await get(`${LIST_QUERY}&pagination[pageSize]=100`)).data

export async function fetchArticle(slug) {
  const { data } = await get(`filters[slug][$eq]=${encodeURIComponent(slug)}&populate=cover`)
  return data[0] ?? null
}

// Every published article with its full content, page by page (used by the prerender)
export async function fetchAllArticles() {
  const all = []
  for (let page = 1; ; page++) {
    const { data, meta } = await get(`populate=cover&sort=publishedAt:desc&pagination[page]=${page}&pagination[pageSize]=100`)
    all.push(...data)
    if (page >= meta.pagination.pageCount) return all
  }
}

// Up to `count` other posts, same category first
export function relatedTo(article, articles, count = 3) {
  const others = articles.filter((a) => a.slug !== article.slug)
  return [...others.filter((a) => a.category === article.category), ...others.filter((a) => a.category !== article.category)].slice(0, count)
}

// The post to lead the blog page with: the newest one marked featured, else the newest
export const pickFeatured = (articles) => articles.find((a) => a.featured) ?? articles[0]

// Local uploads come back as /uploads/...; cloud providers return absolute URLs
export const assetUrl = (url) => (url.startsWith('/') ? STRAPI_URL + url : url)

// A cover as <img> attributes: the requested size as src, every generated size in srcSet
export function coverImage(media, size = 'medium') {
  if (!media?.url) return null
  const formats = Object.values(media.formats ?? {}).sort((a, b) => a.width - b.width)
  const main = media.formats?.[size] ?? media
  return {
    src: assetUrl(main.url),
    srcSet: [...formats, media].map((f) => `${assetUrl(f.url)} ${f.width}w`).join(', '),
    width: main.width,
    height: main.height,
    alt: media.alternativeText || '',
  }
}

export const formatDate = (iso) => new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' })

const blockText = (node) => (node.text ?? '') + (node.children ?? []).map(blockText).join(' ')

export function readTime(blocks = []) {
  const words = blocks.map(blockText).join(' ').split(/\s+/).filter(Boolean).length
  return `${Math.max(1, Math.round(words / 220))} min read`
}

// Heading anchors for the table of contents, keyed by block index so the renderer can reuse them
export function headingAnchors(blocks = []) {
  const used = new Map()
  return blocks.flatMap((block, index) => {
    if (block.type !== 'heading') return []
    const text = blockText(block).trim()
    const base = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'section'
    const n = used.get(base) ?? 0
    used.set(base, n + 1)
    return [{ index, id: n ? `${base}-${n + 1}` : base, text, level: Math.max(block.level, 2) }]
  })
}

// Data the prerender embeds in the page so the first render needs no request
export function readPageData(kind, key) {
  if (typeof document === 'undefined') return null
  try {
    const data = JSON.parse(document.getElementById('page-data')?.textContent || 'null')
    return data?.kind === kind && data.key === key ? data : null
  } catch {
    return null
  }
}
