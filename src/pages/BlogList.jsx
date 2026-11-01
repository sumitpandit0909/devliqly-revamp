import { useEffect, useRef, useState } from 'react'
import { gsap, useGSAP, prefersReducedMotion, remeasure } from '../lib/motion'
import { applyMeta, blogMeta } from '../lib/seo'
import { fetchArticles, pickFeatured, readPageData } from '../lib/blog'
import PostCard from '../components/PostCard'
import Cta from '../components/Cta'

export default function BlogList() {
  const root = useRef(null)
  const [state, setState] = useState(() => {
    const embedded = readPageData('blog', '/blog')
    return embedded ? { status: 'ready', articles: embedded.articles } : { status: 'loading', articles: [] }
  })
  const [category, setCategory] = useState('All')

  useEffect(() => {
    let live = true
    fetchArticles()
      .then((articles) => live && setState({ status: 'ready', articles }))
      .catch(() => live && setState((s) => (s.articles.length ? s : { status: 'error', articles: [] })))
    return () => { live = false }
  }, [])

  const { status, articles } = state

  useEffect(() => {
    applyMeta(blogMeta(articles))
  }, [articles])

  useEffect(() => {
    if (status !== 'loading') remeasure()
  }, [status, category])

  useGSAP(() => {
    if (prefersReducedMotion()) return
    gsap.from('.blog__head > *', { y: 40, autoAlpha: 0, stagger: 0.08, duration: 1, ease: 'power3.out', delay: 0.1 })
  }, { scope: root })

  const featured = pickFeatured(articles)
  const categories = ['All', ...new Set(articles.map((a) => a.category))]
  const rest = articles.filter((a) => a !== featured && (category === 'All' || a.category === category))
  const showFeatured = featured && (category === 'All' || featured.category === category)

  return (
    <main ref={root}>
      <section className="blog">
        <div className="container">
          <header className="blog__head">
            <nav className="crumbs label" aria-label="Breadcrumb">
              <a href="/">Home</a><span aria-hidden="true">/</span><span aria-current="page">Blog</span>
            </nav>
            <h1 className="blog__title">Field <em>notes</em></h1>
            <div className="blog__sub">
              <p className="lead">What we learn building AI agents, chatbots, voice agents and automations for real businesses.</p>
              <a className="blog__rss label" href="/blog/rss.xml" target="_blank" rel="noopener">RSS feed ↗</a>
            </div>
          </header>

          {status === 'loading' && <p className="blog__status" aria-live="polite">Loading posts…</p>}
          {status === 'error' && <p className="blog__status">The blog couldn&apos;t be loaded right now. Please try again in a moment.</p>}
          {status === 'ready' && articles.length === 0 && <p className="blog__status">No posts yet. Check back soon.</p>}

          {articles.length > 0 && (
            <>
              {categories.length > 2 && (
                <div className="blog__filters" role="group" aria-label="Filter posts by category">
                  {categories.map((c) => (
                    <button type="button" key={c} className={`blog-chip ${c === category ? 'is-active' : ''}`} aria-pressed={c === category} onClick={() => setCategory(c)}>
                      {c}
                    </button>
                  ))}
                </div>
              )}

              {showFeatured && (
                <div className="blog__featured">
                  <PostCard article={featured} wide />
                </div>
              )}

              {rest.length > 0 && (
                <ul className="blog__grid">
                  {rest.map((a) => (
                    <li key={a.documentId}><PostCard article={a} /></li>
                  ))}
                </ul>
              )}
              {!showFeatured && rest.length === 0 && <p className="blog__status">No posts in {category} yet.</p>}
            </>
          )}
        </div>
      </section>
      <Cta />
    </main>
  )
}
