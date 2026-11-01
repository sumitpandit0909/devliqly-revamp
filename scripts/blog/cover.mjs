// Branded 1600x900 PNG cover, unique per post (seeded by its slug). Plain Node, no image libraries.
import zlib from 'node:zlib'

const W = 1600
const H = 900
const BG = [10, 10, 15]
const VIOLET = [139, 92, 246]
const SKY = [96, 165, 250]
const LILAC = [196, 181, 253]

function seeded(text) {
  let h = 2166136261
  for (const ch of text) h = Math.imul(h ^ ch.charCodeAt(0), 16777619)
  // mulberry32
  return () => {
    h = (h + 0x6d2b79f5) | 0
    let t = Math.imul(h ^ (h >>> 15), 1 | h)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const CRC = Array.from({ length: 256 }, (_, n) => {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})
const crc32 = (buf) => {
  let c = 0xffffffff
  for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}
function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const body = Buffer.concat([Buffer.from(type), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body))
  return Buffer.concat([len, body, crc])
}

export function coverPng(slug) {
  const rand = seeded(slug)
  const glows = [
    { x: W * (0.55 + rand() * 0.4), y: H * (rand() * 0.4), r: 620 + rand() * 260, c: VIOLET, a: 0.55 },
    { x: W * (rand() * 0.5), y: H * (0.7 + rand() * 0.4), r: 520 + rand() * 220, c: SKY, a: 0.28 },
  ]
  // Concentric rings, like a sound wave, centred somewhere off the right edge
  const ring = { x: W * (0.7 + rand() * 0.3), y: H * (0.25 + rand() * 0.5), gap: 46 + rand() * 30, count: 7 + Math.floor(rand() * 5) }
  const smooth = (e0, e1, x) => { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t) }

  const raw = Buffer.alloc((W * 3 + 1) * H)
  let o = 0
  for (let y = 0; y < H; y++) {
    raw[o++] = 0 // filter: none
    for (let x = 0; x < W; x++) {
      let [r, g, b] = BG
      for (const gl of glows) {
        const d = Math.hypot(x - gl.x, y - gl.y) / gl.r
        const k = gl.a * Math.max(0, 1 - d) ** 2
        r += (gl.c[0] - r) * k; g += (gl.c[1] - g) * k; b += (gl.c[2] - b) * k
      }
      const dr = Math.hypot(x - ring.x, y - ring.y)
      const idx = Math.round(dr / ring.gap)
      if (idx >= 1 && idx <= ring.count) {
        const k = (1 - smooth(0.6, 1.8, Math.abs(dr - idx * ring.gap))) * 0.5 * (1 - idx / (ring.count + 1))
        const c = x / W > 0.5 ? LILAC : SKY
        r += (c[0] - r) * k; g += (c[1] - g) * k; b += (c[2] - b) * k
      }
      // Faint dot grid
      const dx = (x % 40) - 20
      const dy = (y % 40) - 20
      if (dx * dx + dy * dy < 3) { r += 22; g += 22; b += 26 }
      raw[o++] = Math.min(255, r); raw[o++] = Math.min(255, g); raw[o++] = Math.min(255, b)
    }
  }

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(W, 0)
  ihdr.writeUInt32BE(H, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 2 // colour type: RGB
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ])
}
