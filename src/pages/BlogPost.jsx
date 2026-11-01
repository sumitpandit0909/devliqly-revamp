import { useEffect, useRef, useState } from 'react'
import { gsap, useGSAP, prefersReducedMotion, remeasure } from '../lib/motion'
import { applyMeta, articleMeta, SITE_URL } from '../lib/seo'
import { useOpenDemo } from '../lib/demo'
import { coverImage, fetchArticle, fetchArticles, formatDate, headingAnchors, readPageData, readTime, relatedTo } from '../lib/blog'
import Blocks from '../components/Blocks'
import PostCard from '../components/PostCard'
import Magnetic from '../components/Magnetic'
import Cta from '../components/Cta'
import { Arrow } from '../components/Hero'
import NotFound from './NotFound'

const DAY = 864e5

function Share({ url, title }) {
  const [copied, setCopied] = useState(false)
  const u = encodeURIComponent(url)
  const t = encodeURIComponent(title)
  const links = [
    ['LinkedIn', `https://www.linkedin.com/sharing/share-offsite/?url=${u}`],
    ['X', `https://twitter.com/intent/tweet?url=${u}&text=${t}`],
    ['WhatsApp', `https://wa.me/?text=${t}%20${u}`],
  ]
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* clipboard blocked: nothing to do */ }
  }

  return (
    <div className="share">
      <p className="label">Share</p>
      <div className="share__row">
        {links.map(([name, href]) => (
          <a key={name} className="blog-chip" href={href} target="_blank" rel="noopener noreferrer">{name}</a>
        ))}
        <button type="button" className="blog-chip" onClick={copy} aria-live="polite">{copied ? 'Copied ✓' : 'Copy link'}</button>
      </div>
    </div>
  )
}

export default function BlogPost({ slug }) {
  const root = useRef(null)
  const bar = useRef(null)
  const openDemo = useOpenDemo()
  const [state, setState] = useState(() => {
    const embedded = readPageData('post', slug)
    return embedded ? { status: 'ready', article: embedded.article, related: embedded.related } : { status: 'loading', article: null, related: [] }
  })
  const [active, setActive] = useState(null)

  useEffect(() => {
    let live = true
    Promise.all([fetchArticle(slug), fetchArticles().catch(() => [])])
      .then(([article, all]) => {
        if (!live) return
        setState(article ? { status: 'ready', article, related: relatedTo(article, all) } : { status: 'missing', article: null, related: [] })
      })
      .catch(() => live && setState((s) => (s.article ? s : { status: 'error', article: null, related: [] })))
    return () => { live = false }
  }, [slug])

  const { status, article, related } = state
  const toc = article ? headingAnchors(article.content).filter((h) => h.level <= 3) : []

  useEffect(() => {
    if (article) applyMeta(articleMeta(article))
  }, [article])

  useEffect(() => {
    if (status !== 'loading') remeasure()
  }, [status])

  // Reading progress bar and the table-of-contents highlight
  useEffect(() => {
    if (status !== 'ready') return
    const body = root.current?.querySelector('.post__body')
    const heads = toc.map((h) => document.getElementById(h.id)).filter(Boolean)
    let frame = 0
    const update = () => {
      frame = 0
      const r = body.getBoundingClientRect()
      const progress = Math.min(1, Math.max(0, -r.top / Math.max(1, r.height - window.innerHeight * 0.6)))
      if (bar.current) bar.current.style.transform = `scaleX(${progress})`
      const current = heads.filter((el) => el.getBoundingClientRect().top < 160).pop()
      setActive(current?.id ?? null)
    }
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
    }
    // toc is derived from the article, which `status` and `article` already track
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, article])

  useGSAP(() => {
    if (status !== 'ready' || prefersReducedMotion()) return
    gsap.from('.post__head > *', { y: 36, autoAlpha: 0, stagger: 0.07, duration: 0.9, ease: 'power3.out', delay: 0.1 })
    gsap.from('.post__cover', { y: 50, autoAlpha: 0, duration: 1.1, ease: 'power3.out', delay: 0.3 })
  }, { scope: root, dependencies: [status, slug] })

  if (status === 'missing') return <NotFound />

  if (status !== 'ready') {
    return (
      <main className="post">
        <div className="container post__narrow">
          <a href="/blog" className="label sp-back">← All posts</a>
          <p className="blog__status" aria-live="polite">
            {status === 'loading' ? 'Loading post…' : 'This post couldn’t be loaded right now. Please try again in a moment.'}
          </p>
        </div>
      </main>
    )
  }

  const cover = coverImage(article.cover, 'large')
  const url = `${SITE_URL}/blog/${article.slug}`
  const updated = article.updatedAt && new Date(article.updatedAt) - new Date(article.publishedAt) > DAY

  return (
    <main ref={root}>
      <div className="post__progress" aria-hidden="true"><i ref={bar} /></div>
      <article className="post">
        <header className="container post__narrow post__head">
          <nav className="crumbs label" aria-label="Breadcrumb">
            <a href="/">Home</a><span aria-hidden="true">/</span>
            <a href="/blog">Blog</a><span aria-hidden="true">/</span>
            <span aria-current="page">{article.category}</span>
          </nav>
          <h1 className="post__title">{article.title}</h1>
          <p className="lead post__excerpt">{article.excerpt}</p>
          <div className="post__byline">
            <span className="post__avatar" aria-hidden="true">{(article.author || 'D').charAt(0)}</span>
            <div>
              <p className="post__author">{article.author || 'Team Devliqly'}</p>
              <p className="post__dates label">
                <time dateTime={article.publishedAt}>{formatDate(article.publishedAt)}</time>
                <span aria-hidden="true">·</span>
                <span>{readTime(article.content)}</span>
                {updated && <><span aria-hidden="true">·</span><span>Updated <time dateTime={article.updatedAt}>{formatDate(article.updatedAt)}</time></span></>}
              </p>
            </div>
          </div>
        </header>

        {cover && (
          <figure className="container post__cover">
            <img src={cover.src} srcSet={cover.srcSet} sizes="(max-width: 1440px) 100vw, 1440px" width={cover.width} height={cover.height} alt={cover.alt} fetchPriority="high" />
          </figure>
        )}

        <div className="container post__layout">
          <aside className="post__aside">
            {toc.length > 1 && (
              <nav className="toc" aria-label="On this page">
                <details open>
                  <summary className="label">On this page</summary>
                  <ol>
                    {toc.map((h) => (
                      <li key={h.id} className={`toc__l${h.level} ${active === h.id ? 'is-active' : ''}`}>
                        <a href={`#${h.id}`}>{h.text}</a>
                      </li>
                    ))}
                  </ol>
                </details>
              </nav>
            )}
            <Share url={url} title={article.title} />
          </aside>

          <div className="post__main">
            <div className="post__body">
              <Blocks content={article.content} />
            </div>

            <footer className="post__foot">
              <div className="post__tags">
                <span className="label">Filed under</span>
                <a className="blog-chip" href="/blog">{article.category}</a>
              </div>
              <Share url={url} title={article.title} />
              <div className="author-box">
                <span className="post__avatar post__avatar--lg" aria-hidden="true">{(article.author || 'D').charAt(0)}</span>
                <div>
                  <p className="author-box__name">{article.author || 'Team Devliqly'}</p>
                  <p className="author-box__bio">We design and build AI agents, chatbots, voice and call agents and custom automations for growing businesses.</p>
                  <Magnetic>
                    <button type="button" className="btn" onClick={() => openDemo()}>Book a free demo <Arrow /></button>
                  </Magnetic>
                </div>
              </div>
            </footer>
          </div>
        </div>
      </article>

      {related.length > 0 && (
        <section className="section post__related" aria-labelledby="related-title">
          <div className="container">
            <div className="post__related-head">
              <h2 className="h2" id="related-title">Keep <em>reading</em></h2>
              <a href="/blog" className="label sp-back">All posts →</a>
            </div>
            <ul className="blog__grid">
              {related.map((a) => (
                <li key={a.documentId}><PostCard article={a} headingLevel={3} /></li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <Cta />
    </main>
  )
}
