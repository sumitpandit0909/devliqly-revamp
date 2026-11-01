import { coverImage, formatDate } from '../lib/blog'
import { Arrow } from './Hero'

// Blog post teaser; `wide` is the featured layout with the image beside the text
export default function PostCard({ article, wide = false, headingLevel = 2, sizes = '(max-width: 899px) 100vw, 33vw' }) {
  const cover = coverImage(article.cover, wide ? 'large' : 'medium')
  const Title = `h${headingLevel}`

  return (
    <a href={`/blog/${article.slug}`} className={`post-card ${wide ? 'post-card--wide' : ''}`} data-cursor="Read">
      <div className="post-card__media">
        {cover ? (
          <img src={cover.src} srcSet={cover.srcSet} sizes={wide ? '(max-width: 899px) 100vw, 60vw' : sizes} width={cover.width} height={cover.height} alt={cover.alt} loading={wide ? 'eager' : 'lazy'} decoding="async" />
        ) : (
          <span aria-hidden="true">{article.category}</span>
        )}
      </div>
      <div className="post-card__body">
        <div className="post-card__meta label">
          {wide && <span className="post-card__flag">Featured</span>}
          <span>{article.category}</span>
          <time dateTime={article.publishedAt}>{formatDate(article.publishedAt)}</time>
        </div>
        <Title className="post-card__title">{article.title}</Title>
        <p className="post-card__excerpt">{article.excerpt}</p>
        <span className="post-card__more">Read post <Arrow /></span>
      </div>
    </a>
  )
}
