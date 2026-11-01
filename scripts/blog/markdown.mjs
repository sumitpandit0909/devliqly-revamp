// Converts the Markdown subset the blog uses into Strapi "blocks" rich text, plus front matter parsing.
// Supported: ## / ### headings, paragraphs, - and 1. lists, > quotes, ``` code fences,
// and inline **bold**, *italic*, `code`, [text](url).

const INLINE = /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\))/g

export function inline(text) {
  const out = []
  let last = 0
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) out.push({ type: 'text', text: text.slice(last, m.index) })
    if (m[2]) out.push({ type: 'text', text: m[2], bold: true })
    else if (m[3]) out.push({ type: 'text', text: m[3], italic: true })
    else if (m[4]) out.push({ type: 'text', text: m[4], code: true })
    else out.push({ type: 'link', url: m[6], children: [{ type: 'text', text: m[5] }] })
    last = m.index + m[0].length
  }
  if (last < text.length) out.push({ type: 'text', text: text.slice(last) })
  return out.length ? out : [{ type: 'text', text: '' }]
}

export function toBlocks(markdown) {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let para = []
  let list = null

  const flushPara = () => {
    if (para.length) blocks.push({ type: 'paragraph', children: inline(para.join(' ')) })
    para = []
  }
  const flushList = () => {
    if (list) blocks.push(list)
    list = null
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (line.startsWith('```')) {
      flushPara(); flushList()
      const code = []
      while (++i < lines.length && !lines[i].trim().startsWith('```')) code.push(lines[i])
      blocks.push({ type: 'code', children: [{ type: 'text', text: code.join('\n') }] })
      continue
    }
    if (!line) { flushPara(); flushList(); continue }

    const heading = line.match(/^(#{2,4})\s+(.*)$/)
    const bullet = line.match(/^[-*]\s+(.*)$/)
    const numbered = line.match(/^\d+[.)]\s+(.*)$/)
    const quote = line.match(/^>\s?(.*)$/)

    if (heading) {
      flushPara(); flushList()
      blocks.push({ type: 'heading', level: heading[1].length, children: inline(heading[2]) })
    } else if (bullet || numbered) {
      flushPara()
      const format = bullet ? 'unordered' : 'ordered'
      if (list?.format !== format) { flushList(); list = { type: 'list', format, children: [] } }
      list.children.push({ type: 'list-item', children: inline((bullet || numbered)[1]) })
    } else if (quote) {
      flushPara(); flushList()
      blocks.push({ type: 'quote', children: inline(quote[1]) })
    } else {
      flushList()
      para.push(line)
    }
  }
  flushPara(); flushList()
  return blocks
}

// "---\nkey: value\n---\nbody" → { meta, body }
export function frontMatter(source) {
  const m = source.replace(/\r\n/g, '\n').match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/)
  if (!m) throw new Error('The file must start with a --- front matter block')
  const meta = {}
  for (const row of m[1].split('\n')) {
    const kv = row.match(/^(\w+):\s*(.*)$/)
    if (kv) meta[kv[1]] = kv[2].trim().replace(/^(["'])(.*)\1$/, '$2')
  }
  return { meta, body: m[2] }
}

const textOf = (node) => (node.text ?? '') + (node.children ?? []).map(textOf).join(' ')
export const wordCount = (blocks) => blocks.map(textOf).join(' ').split(/\s+/).filter(Boolean).length
