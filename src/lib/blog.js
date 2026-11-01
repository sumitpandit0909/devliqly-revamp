import { ScrollTrigger, lenisRef } from './motion'

// Blog content comes from the Strapi app in /cms. Without VITE_STRAPI_URL the blog stays switched off.
export const STRAPI_URL = (import.meta.env.VITE_STRAPI_URL || '').replace(/\/+$/, '')
export const BLOG_ENABLED = Boolean(STRAPI_URL)

const LIST_FIELDS = 'fields[0]=title&fields[1]=slug&fields[2]=excerpt&fields[3]=category&fields[4]=publishedAt&fields[5]=author'

async function get(query) {
  const res = await fetch(`${STRAPI_URL}/api/articles?${query}`)
  if (!res.ok) throw new Error(`Strapi responded ${res.status}`)
  return (await res.json()).data
}

export const fetchArticles = () => get(`${LIST_FIELDS}&populate[cover][fields][0]=url&populate[cover][fields][1]=alternativeText&sort=publishedAt:desc&pagination[pageSize]=50`)

export async function fetchArticle(slug) {
  const [article] = await get(`filters[slug][$eq]=${encodeURIComponent(slug)}&populate=cover`)
  return article ?? null
}

// Local uploads come back as /uploads/...; cloud providers return absolute URLs
export const mediaUrl = (media) => (media?.url ? (media.url.startsWith('/') ? STRAPI_URL + media.url : media.url) : null)

export const formatDate = (iso) => new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

const blockText = (node) => (node.text ?? '') + (node.children ?? []).map(blockText).join(' ')

export function readTime(blocks = []) {
  const words = blocks.map(blockText).join(' ').split(/\s+/).filter(Boolean).length
  return `${Math.max(1, Math.round(words / 220))} min read`
}

// Content arrives after the route change measured the page, so re-measure scroll triggers and the smooth scroller
export function remeasure() {
  requestAnimationFrame(() => {
    ScrollTrigger.refresh()
    lenisRef.current?.resize()
  })
}
