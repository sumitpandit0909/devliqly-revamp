import { useEffect, useState } from 'react'
import { setPageMeta } from '../lib/router'
import { fetchArticle, formatDate, mediaUrl, remeasure, readTime } from '../lib/blog'
import Blocks from '../components/Blocks'
import Cta from '../components/Cta'
import NotFound from './NotFound'

export default function BlogPost({ slug }) {
  const [state, setState] = useState({ status: 'loading', article: null })

  useEffect(() => {
    let live = true
    fetchArticle(slug)
      .then((article) => {
        if (!live) return
        setState({ status: article ? 'ready' : 'missing', article })
        if (article) setPageMeta(`${article.title} | DEVLIQLY`, article.excerpt)
      })
      .catch(() => live && setState({ status: 'error', article: null }))
    return () => { live = false }
  }, [slug])

  useEffect(() => {
    if (state.status !== 'loading') remeasure()
  }, [state.status])

  const { status, article } = state
  if (status === 'missing') return <NotFound />

  if (status !== 'ready') {
    return (
      <main className="post">
        <div className="container post__inner">
          <a href="/blog" className="label sp-back">← All posts</a>
          <p className="blog__status" aria-live="polite">
            {status === 'loading' ? 'Loading post…' : 'This post couldn’t be loaded right now. Please try again in a moment.'}
          </p>
        </div>
      </main>
    )
  }

  const cover = mediaUrl(article.cover)

  return (
    <main>
      <article className="post">
        <div className="container post__inner">
          <a href="/blog" className="label sp-back">← All posts</a>
          <div className="post__meta label">
            <span>{article.category}</span>
            <time dateTime={article.publishedAt}>{formatDate(article.publishedAt)}</time>
            <span>{readTime(article.content)}</span>
          </div>
          <h1 className="post__title">{article.title}</h1>
          <p className="lead post__excerpt">{article.excerpt}</p>
          {article.author && <p className="post__author">By {article.author}</p>}
        </div>
        {cover && (
          <div className="container post__cover">
            <img src={cover} alt={article.cover.alternativeText || ''} />
          </div>
        )}
        <div className="container post__inner">
          <div className="post__body">
            <Blocks content={article.content} />
          </div>
        </div>
      </article>
      <Cta />
    </main>
  )
}
