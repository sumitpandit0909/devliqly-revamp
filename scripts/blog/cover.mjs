// 1600x900 PNG cover for a blog post: the title, its category and a topic illustration in the site's style.
// Drawn as SVG and rendered with resvg using the site's own fonts (Syne for headings, Inter for text).
import { createRequire } from 'node:module'
import { Resvg } from '@resvg/resvg-js'

const require = createRequire(import.meta.url)
const FONTS = {
  fontFiles: [
    require.resolve('@expo-google-fonts/syne/800ExtraBold/Syne_800ExtraBold.ttf'),
    require.resolve('@expo-google-fonts/inter/500Medium/Inter_500Medium.ttf'),
    require.resolve('@expo-google-fonts/inter/600SemiBold/Inter_600SemiBold.ttf'),
  ],
  loadSystemFonts: false,
  defaultFontFamily: 'Inter',
}

const W = 1600
const H = 900
const TEXT_X = 96
const TEXT_MAX_W = 860

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

// Line art in a 400x400 box; `ink` is the violet→sky stroke, `soft` a translucent violet fill
const LINE = 'fill="none" stroke="url(#ink)" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"'
const SOFT = 'fill="rgba(139,92,246,0.22)"'
export const MOTIFS = {
  chat: `
    <path d="M70 70 h220 a40 40 0 0 1 40 40 v90 a40 40 0 0 1 -40 40 h-130 l-60 50 v-50 h-30 a40 40 0 0 1 -40 -40 v-90 a40 40 0 0 1 40 -40 z" ${LINE}/>
    <circle cx="125" cy="155" r="13" fill="#c4b5fd"/><circle cx="180" cy="155" r="13" fill="#a5b4fc"/><circle cx="235" cy="155" r="13" fill="#93c5fd"/>
    <path d="M200 260 h110 a30 30 0 0 1 30 30 v40 a30 30 0 0 1 -30 30 h-10 v34 l-42 -34 h-58 a30 30 0 0 1 -30 -30 v-40 a30 30 0 0 1 30 -30 z" ${SOFT} stroke="url(#ink)" stroke-width="8"/>`,
  calendar: `
    <rect x="50" y="80" width="300" height="270" rx="32" ${LINE}/>
    <path d="M50 150 h300 M130 50 v60 M270 50 v60" ${LINE}/>
    ${[0, 1, 2, 3].flatMap((c) => [0, 1].map((r) => `<rect x="${92 + c * 58}" y="${185 + r * 58}" width="34" height="34" rx="8" fill="rgba(196,181,253,${0.18 + (c + r) * 0.06})"/>`)).join('')}
    <circle cx="300" cy="310" r="62" fill="#0f0f16" stroke="url(#ink)" stroke-width="12"/>
    <path d="M272 310 l20 20 l36 -40" ${LINE}/>`,
  phone: `
    <rect x="110" y="40" width="160" height="320" rx="34" ${LINE}/>
    <path d="M165 80 h50" ${LINE}/>
    <circle cx="190" cy="315" r="10" fill="#c4b5fd"/>
    <path d="M300 150 a60 60 0 0 1 0 100 M330 115 a105 105 0 0 1 0 170" ${LINE}/>`,
  waveform: [30, 70, 120, 180, 240, 160, 210, 120, 80, 140, 60, 30]
    .map((h, i) => `<rect x="${44 + i * 28}" y="${200 - h / 2}" width="14" height="${h}" rx="7" fill="url(#ink)"/>`).join(''),
  workflow: `
    <path d="M140 110 h120 M120 150 l60 110 M280 150 l-60 110" ${LINE} stroke-dasharray="2 22"/>
    <rect x="40" y="60" width="100" height="100" rx="24" ${LINE}/>
    <rect x="260" y="60" width="100" height="100" rx="24" ${SOFT} stroke="url(#ink)" stroke-width="12"/>
    <rect x="150" y="250" width="100" height="100" rx="24" ${LINE}/>
    <path d="M70 110 h40 M290 95 l20 15 l-20 15 M180 300 h40" ${LINE}/>`,
  agent: `
    <circle cx="200" cy="200" r="150" ${LINE} stroke-dasharray="40 26" opacity="0.6"/>
    <circle cx="200" cy="200" r="110" ${LINE} opacity="0.85"/>
    <path d="M200 132 q10 58 68 68 q-58 10 -68 68 q-10 -58 -68 -68 q58 -10 68 -68 z" fill="url(#ink)"/>
    <path d="M276 128 q4 20 24 24 q-20 4 -24 24 q-4 -20 -24 -24 q20 -4 24 -24 z" fill="#c4b5fd"/>
    <circle cx="330" cy="95" r="14" fill="#93c5fd"/><circle cx="70" cy="300" r="10" fill="#c4b5fd"/>`,
  cart: `
    <path d="M40 80 h50 l45 180 h180 l40 -130 h-245" ${LINE}/>
    <path d="M150 200 h165" ${LINE} opacity="0.6"/>
    <circle cx="160" cy="320" r="26" ${LINE}/><circle cx="300" cy="320" r="26" ${LINE}/>
    <rect x="175" y="40" width="90" height="70" rx="14" ${SOFT} stroke="url(#ink)" stroke-width="8"/>`,
  clinic: `
    <rect x="60" y="60" width="200" height="200" rx="44" ${SOFT} stroke="url(#ink)" stroke-width="12"/>
    <path d="M160 105 v110 M105 160 h110" ${LINE}/>
    <path d="M40 320 h110 l25 -50 l35 90 l30 -70 l20 30 h100" ${LINE}/>`,
  property: `
    <path d="M60 190 l140 -120 l140 120" ${LINE}/>
    <path d="M95 165 v175 h210 v-175" ${LINE}/>
    <rect x="165" y="240" width="70" height="100" rx="12" ${SOFT} stroke="url(#ink)" stroke-width="10"/>
    <circle cx="300" cy="90" r="22" ${LINE}/><path d="M318 106 l40 40 M345 133 l-14 14" ${LINE}/>`,
  education: `
    <path d="M30 160 l170 -80 l170 80 l-170 80 z" ${SOFT} stroke="url(#ink)" stroke-width="12" stroke-linejoin="round"/>
    <path d="M100 195 v80 c0 40 200 40 200 0 v-80" ${LINE}/>
    <path d="M340 175 v95" ${LINE}/><circle cx="340" cy="290" r="16" fill="#93c5fd"/>`,
  chart: `
    <path d="M50 50 v300 h300" ${LINE}/>
    <rect x="100" y="250" width="44" height="100" rx="10" fill="rgba(196,181,253,0.35)"/>
    <rect x="170" y="200" width="44" height="150" rx="10" fill="rgba(165,180,252,0.45)"/>
    <rect x="240" y="140" width="44" height="210" rx="10" fill="url(#ink)"/>
    <path d="M95 210 l70 -50 l60 30 l100 -110 M285 80 h40 v40" ${LINE}/>`,
  funnel: `
    <path d="M40 70 h320 l-120 140 v110 l-80 40 v-150 z" ${LINE}/>
    <path d="M85 120 h230" ${LINE} opacity="0.5"/>
    <circle cx="120" cy="40" r="14" fill="#c4b5fd"/><circle cx="200" cy="30" r="14" fill="#a5b4fc"/><circle cx="280" cy="40" r="14" fill="#93c5fd"/>
    <circle cx="200" cy="390" r="10" fill="url(#ink)"/>`,
  headset: `
    <path d="M80 230 v-40 a120 120 0 0 1 240 0 v40" ${LINE}/>
    <rect x="55" y="210" width="60" height="100" rx="24" ${SOFT} stroke="url(#ink)" stroke-width="12"/>
    <rect x="285" y="210" width="60" height="100" rx="24" ${SOFT} stroke="url(#ink)" stroke-width="12"/>
    <path d="M315 310 c0 50 -40 70 -100 70 h-20" ${LINE}/><circle cx="180" cy="380" r="16" fill="url(#ink)"/>`,
}

const CATEGORY_MOTIF = { Chatbots: 'chat', Voice: 'waveform', Automation: 'workflow', 'AI Agents': 'agent', Company: 'agent' }

function textWidth(text, size) {
  const probe = new Resvg(
    `<svg xmlns="http://www.w3.org/2000/svg" width="4000" height="300"><text x="0" y="200" font-family="Syne" font-weight="800" font-size="${size}" letter-spacing="${-size * 0.02}">${esc(text)}</text></svg>`,
    { font: FONTS },
  )
  return probe.getBBox()?.width ?? 0
}

const wrap = (words, size) => {
  const lines = []
  let line = ''
  for (const w of words) {
    const next = line ? `${line} ${w}` : w
    if (line && textWidth(next, size) > TEXT_MAX_W) {
      lines.push(line)
      line = w
    } else line = next
  }
  return [...lines, line]
}

// Largest size that fits the title in three lines, else four; very long titles keep every word at the smallest size
function layoutTitle(title) {
  const words = title.split(/\s+/)
  let lines
  for (let size = 96; size >= 40; size -= 4) {
    lines = wrap(words, size)
    if (lines.length <= 3 || (lines.length <= 4 && size <= 72)) return { size, lines }
  }
  return { size: 40, lines }
}

export function coverPng({ title, category, motif }) {
  const art = MOTIFS[motif] ?? MOTIFS[CATEGORY_MOTIF[category] ?? 'agent']
  const { size, lines } = layoutTitle(title)
  const lineH = size * 1.06
  const blockH = lineH * lines.length
  const top = 300 + (430 - blockH) / 2 + size * 0.8
  const label = category.toUpperCase()
  const labelW = 44 + label.length * 15

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <radialGradient id="glowV" cx="1250" cy="160" r="760" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#8b5cf6" stop-opacity="0.55"/><stop offset="1" stop-color="#8b5cf6" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowS" cx="160" cy="900" r="620" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#60a5fa" stop-opacity="0.28"/><stop offset="1" stop-color="#60a5fa" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="ink" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#c4b5fd"/><stop offset="0.5" stop-color="#a78bfa"/><stop offset="1" stop-color="#60a5fa"/>
    </linearGradient>
    <linearGradient id="titleInk" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#a78bfa"/><stop offset="1" stop-color="#60a5fa"/>
    </linearGradient>
    <pattern id="dots" width="40" height="40" patternUnits="userSpaceOnUse"><circle cx="20" cy="20" r="1.6" fill="rgba(255,255,255,0.09)"/></pattern>
  </defs>
  <rect width="${W}" height="${H}" fill="#0a0a0f"/>
  <rect width="${W}" height="${H}" fill="url(#glowV)"/>
  <rect width="${W}" height="${H}" fill="url(#glowS)"/>
  <rect width="${W}" height="${H}" fill="url(#dots)"/>
  ${[260, 340, 420, 500].map((r, i) => `<circle cx="1250" cy="470" r="${r}" fill="none" stroke="rgba(196,181,253,${0.16 - i * 0.035})" stroke-width="2"/>`).join('')}

  <g transform="translate(${TEXT_X} 92)">
    <rect width="54" height="54" rx="12" fill="#0a0a0f" stroke="rgba(255,255,255,0.12)"/>
    <path d="M15.2 11.8 h11.8 a15.2 15.2 0 0 1 0 30.4 H15.2 z" fill="none" stroke="#8b5cf6" stroke-width="5.9" stroke-linejoin="round"/>
    <circle cx="27" cy="27" r="4.2" fill="#fff"/>
    <text x="74" y="38" font-family="Syne" font-weight="800" font-size="30" fill="#f4f3f8" letter-spacing="1">DEVLIQLY</text>
  </g>

  <g transform="translate(${TEXT_X} 214)">
    <rect width="${labelW}" height="46" rx="23" fill="rgba(139,92,246,0.18)" stroke="rgba(139,92,246,0.7)" stroke-width="1.5"/>
    <text x="${labelW / 2}" y="30" text-anchor="middle" font-family="Inter" font-weight="600" font-size="19" letter-spacing="3" fill="#c4b5fd">${esc(label)}</text>
  </g>

  ${lines.map((l, i) => `<text x="${TEXT_X}" y="${top + i * lineH}" font-family="Syne" font-weight="800" font-size="${size}" letter-spacing="${-size * 0.02}" fill="${i === lines.length - 1 ? 'url(#titleInk)' : '#f4f3f8'}">${esc(l)}</text>`).join('\n  ')}

  <text x="${TEXT_X}" y="836" font-family="Inter" font-weight="500" font-size="24" fill="#8f8da3">www.devliqly.in/blog</text>

  <g transform="translate(1000 220)">
    <rect width="500" height="500" rx="48" fill="rgba(21,21,29,0.82)" stroke="rgba(255,255,255,0.12)" stroke-width="2"/>
    <g transform="translate(50 50)">${art}</g>
  </g>
</svg>`

  return new Resvg(svg, { font: FONTS, fitTo: { mode: 'width', value: W } }).render().asPng()
}
