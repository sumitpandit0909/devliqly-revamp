import { assetUrl, headingAnchors } from '../lib/blog'

// Renders Strapi's "blocks" rich text (paragraphs, headings, lists, quotes, code, images, links)
function Inline({ node }) {
  if (node.type === 'link') {
    const external = /^https?:\/\//.test(node.url)
    return (
      <a href={node.url} {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>
        {node.children.map((c, i) => <Inline node={c} key={i} />)}
      </a>
    )
  }
  let out = node.text
  if (node.code) out = <code>{out}</code>
  if (node.bold) out = <strong>{out}</strong>
  if (node.italic) out = <em>{out}</em>
  if (node.underline) out = <u>{out}</u>
  if (node.strikethrough) out = <s>{out}</s>
  return out
}

const inlines = (children = []) => children.map((c, i) => <Inline node={c} key={i} />)

function Block({ block, id }) {
  switch (block.type) {
    case 'heading': {
      // The post title is the h1, so content headings start at h2
      const Tag = `h${Math.min(Math.max(block.level, 2), 6)}`
      return <Tag id={id} data-scroll-offset="-110">{inlines(block.children)}</Tag>
    }
    case 'list': {
      const Tag = block.format === 'ordered' ? 'ol' : 'ul'
      return (
        <Tag>
          {block.children.map((item, i) => (
            <li key={i}>{item.type === 'list' ? <Block block={item} /> : inlines(item.children)}</li>
          ))}
        </Tag>
      )
    }
    case 'quote':
      return <blockquote>{inlines(block.children)}</blockquote>
    case 'code':
      return <pre><code>{block.children.map((c) => c.text).join('')}</code></pre>
    case 'image':
      return (
        <figure>
          <img src={assetUrl(block.image.url)} alt={block.image.alternativeText || ''} width={block.image.width} height={block.image.height} loading="lazy" decoding="async" />
          {block.image.caption && <figcaption>{block.image.caption}</figcaption>}
        </figure>
      )
    default:
      return <p>{inlines(block.children)}</p>
  }
}

export default function Blocks({ content = [] }) {
  const ids = new Map(headingAnchors(content).map((h) => [h.index, h.id]))
  return content.map((block, i) => <Block block={block} id={ids.get(i)} key={i} />)
}
