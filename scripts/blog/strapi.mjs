// Blog CLI for the CMS at blog.devliqly.in, used by the daily writing routine.
//   node scripts/blog/strapi.mjs list            every article (drafts and published), newest first
//   node scripts/blog/strapi.mjs draft <file.md> save a Markdown article with a generated cover as a draft
//   node scripts/blog/strapi.mjs cover <file.md> <out.png>  only render the cover, e.g. to replace one by hand
// Needs STRAPI_TOKEN (a Strapi API token: Article find/findOne/create, Upload upload).
// STRAPI_URL defaults to https://blog.devliqly.in.
import fs from 'node:fs'
import { MOTIFS, coverPng } from './cover.mjs'
import { frontMatter, toBlocks, wordCount } from './markdown.mjs'

const STRAPI_URL = (process.env.STRAPI_URL || 'https://blog.devliqly.in').replace(/\/+$/, '')
const TOKEN = process.env.STRAPI_TOKEN
const CATEGORIES = ['AI Agents', 'Chatbots', 'Voice', 'Automation', 'Company']
const LIMITS = { title: 120, excerpt: 280, seoTitle: 70, seoDescription: 170 }
const MIN_WORDS = 600

class CliError extends Error {}
const fail = (msg) => {
  throw new CliError(msg)
}

async function api(path, init = {}) {
  const res = await fetch(`${STRAPI_URL}${path}`, { ...init, headers: { Authorization: `Bearer ${TOKEN}`, ...init.headers } })
  const body = await res.json().catch(() => null)
  if (!res.ok) fail(`${init.method || 'GET'} ${path} → ${res.status} ${JSON.stringify(body?.error ?? body)}`)
  return body
}

// The CMS sleeps when idle on Render's free tier; wait up to ~2 minutes for it to wake
async function wake() {
  for (let i = 0; i < 12; i++) {
    try {
      const res = await fetch(`${STRAPI_URL}/_health`, { signal: AbortSignal.timeout(30000) })
      if (res.ok) return
    } catch { /* still waking */ }
    await new Promise((r) => setTimeout(r, 10000))
  }
  fail(`${STRAPI_URL} did not wake up`)
}

async function allArticles() {
  // status=draft returns the latest version of every article, published ones included
  const { data } = await api('/api/articles?status=draft&fields[0]=title&fields[1]=slug&fields[2]=category&fields[3]=publishedAt&fields[4]=createdAt&sort=createdAt:desc&pagination[pageSize]=500')
  return data
}

const slugify = (s) => s.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 80).replace(/-$/, '')

async function list() {
  const published = new Set((await api('/api/articles?fields[0]=slug&pagination[pageSize]=500')).data.map((a) => a.slug))
  const articles = await allArticles()
  if (!articles.length) return console.log('No articles yet.')
  for (const a of articles) {
    console.log(`${a.createdAt.slice(0, 10)}  [${published.has(a.slug) ? 'published' : 'draft    '}]  ${a.category.padEnd(10)}  ${a.title}`)
  }
}

function readArticle(file) {
  if (!file || !fs.existsSync(file)) fail('Pass the path of a Markdown file')
  const { meta, body } = frontMatter(fs.readFileSync(file, 'utf8'))
  for (const key of ['title', 'excerpt', 'category']) if (!meta[key]) fail(`Front matter is missing "${key}"`)
  for (const [key, max] of Object.entries(LIMITS)) if (meta[key] && meta[key].length > max) fail(`"${key}" is ${meta[key].length} characters; the limit is ${max}`)
  if (!CATEGORIES.includes(meta.category)) fail(`"category" must be one of: ${CATEGORIES.join(', ')}`)
  if (meta.coverMotif && !MOTIFS[meta.coverMotif]) fail(`"coverMotif" must be one of: ${Object.keys(MOTIFS).join(', ')}`)
  return { meta, body }
}

const coverFor = (meta) => coverPng({ title: meta.title, category: meta.category, motif: meta.coverMotif })

function cover(file, out) {
  if (!out) fail('Pass the output PNG path')
  fs.writeFileSync(out, coverFor(readArticle(file).meta))
  console.log(`Wrote ${out}`)
}

async function draft(file) {
  const { meta, body } = readArticle(file)
  const content = toBlocks(body)
  const words = wordCount(content)
  if (words < MIN_WORDS) fail(`The article has ${words} words; write at least ${MIN_WORDS}`)
  if (content.some((b) => b.type === 'heading' && b.level === 1)) fail('Use ## for section headings; the title is already the page heading')

  const existing = await allArticles()
  if (existing.some((a) => a.title.toLowerCase() === meta.title.toLowerCase())) fail('An article with this title already exists')
  const taken = new Set(existing.map((a) => a.slug))
  const base = slugify(meta.slug || meta.title)
  let slug = base
  for (let n = 2; taken.has(slug); n++) slug = `${base}-${n}`

  const form = new FormData()
  form.append('files', new Blob([coverFor(meta)], { type: 'image/png' }), `${slug}.png`)
  form.append('fileInfo', JSON.stringify({ name: `${slug}.png`, alternativeText: meta.coverAlt || `Cover image for "${meta.title}"` }))
  const [cover] = await api('/api/upload', { method: 'POST', body: form })

  // Strapi 5 publishes new entries unless the request asks for a draft
  const { data } = await api('/api/articles?status=draft', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      data: {
        title: meta.title,
        slug,
        excerpt: meta.excerpt,
        category: meta.category,
        author: meta.author || 'Team Devliqly',
        seoTitle: meta.seoTitle || undefined,
        seoDescription: meta.seoDescription || undefined,
        cover: cover.id,
        content,
      },
    }),
  })

  console.log(`Saved draft "${data.title}" (${words} words)`)
  console.log(`Review and publish: ${STRAPI_URL}/admin/content-manager/collection-types/api::article.article/${data.documentId}`)
}

async function main() {
  const [command, arg, out] = process.argv.slice(2)
  if (command === 'cover') return cover(arg, out)
  if (!TOKEN) fail('Set STRAPI_TOKEN to a Strapi API token')
  if (!['list', 'draft'].includes(command)) fail('Usage: node scripts/blog/strapi.mjs list | draft <file.md> | cover <file.md> <out.png>')
  await wake()
  await (command === 'list' ? list() : draft(arg))
}

main().catch((err) => {
  console.error(`Error: ${err.message}`)
  process.exitCode = 1
})
