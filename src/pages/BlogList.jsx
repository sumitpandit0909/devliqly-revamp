import { useEffect, useState } from 'react'
import { setPageMeta } from '../lib/router'
import { fetchArticles, formatDate, mediaUrl, remeasure } from '../lib/blog'
import { Arrow } from '../components/Hero'

export default function BlogList() {
  const [state, setState] = useState({ status: 'loading', articles: [] })

  useEffect(() => {
    setPageMeta('Blog | DEVLIQLY', 'Notes from Devliqly on AI agents, chatbots, voice agents and automation for growing businesses.')
    let live = true
    fetchArticles()
      .then((articles) => live && setState({ status: 'ready', articles }))
      .catch(() => live && setState({ status: 'error', articles: [] }))
    return () => { live = false }
  }, [])

  useEffect(() => {
    if (state.status !== 'loading') remeasure()
  }, [state.status])

  const { status, articles } = state

  return (
    <main className="blog">
      <div className="container">
        <p className="label">( Blog )</p>
        <h1 className="blog__title">Field <em>notes</em></h1>
        <p className="lead blog__intro">What we learn building AI agents, chatbots and automations for real businesses.</p>

        {status === 'loading' && <p className="blog__status" aria-live="polite">Loading posts…</p>}
        {status === 'error' && <p className="blog__status">The blog couldn&apos;t be loaded right now. Please try again in a moment.</p>}
        {status === 'ready' && articles.length === 0 && <p className="blog__status">No posts yet. Check back soon.</p>}

        {articles.length > 0 && (
          <ul className="blog__grid">
            {articles.map((a) => {
              const cover = mediaUrl(a.cover)
              return (
                <li key={a.documentId}>
                  <a href={`/blog/${a.slug}`} className="post-card" data-cursor="Read">
                    <div className="post-card__media">
                      {cover ? <img src={cover} alt={a.cover.alternativeText || ''} loading="lazy" /> : <span aria-hidden="true">{a.category}</span>}
                    </div>
                    <div className="post-card__meta label">
                      <span>{a.category}</span>
                      <time dateTime={a.publishedAt}>{formatDate(a.publishedAt)}</time>
                    </div>
                    <h2 className="post-card__title">{a.title}</h2>
                    <p className="post-card__excerpt">{a.excerpt}</p>
                    <span className="post-card__more">Read post <Arrow /></span>
                  </a>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </main>
  )
}
