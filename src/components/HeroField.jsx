import { useEffect, useRef } from 'react'
import { prefersReducedMotion } from '../lib/motion'

const GAP = 30          // dot spacing (px)
const RADIUS = 180      // pointer influence radius
const PUSH = 22         // max displacement from the pointer
const PULSE_EVERY = 4200 // ms between automatic "voice pulses" from the orb

const rgb = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).split(',').map((v) => Number(v.trim()))

// Interactive dot field: dots swell, glow and part around the cursor;
// clicks (and the orb, periodically) send out ripples that travel across the grid.
export default function HeroField() {
  const ref = useRef(null)

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas.getContext('2d')
    const A = rgb('--accent-rgb')
    const B = rgb('--accent-2-rgb')
    const reduce = prefersReducedMotion()

    let w = 0, h = 0, dots = [], raf = 0, running = false, lastPulse = 0
    const pointer = { x: -9999, y: -9999, tx: -9999, ty: -9999, on: 0, onT: 0 }
    const ripples = []

    const resize = () => {
      const r = canvas.getBoundingClientRect()
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = r.width; h = r.height
      canvas.width = w * dpr; canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      dots = []
      const ox = (w % GAP) / 2, oy = (h % GAP) / 2
      for (let y = oy; y < h; y += GAP) {
        for (let x = ox; x < w; x += GAP) dots.push({ x, y, dx: 0, dy: 0, vx: 0, vy: 0 })
      }
      if (reduce) draw(0)
    }

    const toLocal = (e) => {
      const r = canvas.getBoundingClientRect()
      const x = e.clientX - r.left, y = e.clientY - r.top
      return { x, y, inside: x >= 0 && y >= 0 && x <= r.width && y <= r.height }
    }

    const onMove = (e) => {
      const p = toLocal(e)
      if (!p.inside) { pointer.onT = 0; return }
      if (pointer.x < -999) { pointer.x = p.x; pointer.y = p.y }
      pointer.tx = p.x; pointer.ty = p.y; pointer.onT = 1
    }
    const onDown = (e) => {
      const p = toLocal(e)
      if (p.inside) ripples.push({ x: p.x, y: p.y, r: 0, s: 1 })
    }
    const onLeave = () => { pointer.onT = 0 }

    // Ripple from the centre of the hero orb, like a voice pulse
    const orbPulse = () => {
      const orb = document.querySelector('.hero .orb__core')
      if (!orb) return
      const o = orb.getBoundingClientRect(), c = canvas.getBoundingClientRect()
      ripples.push({ x: o.left + o.width / 2 - c.left, y: o.top + o.height / 2 - c.top, r: o.width / 2, s: 0.7 })
    }

    function draw(t) {
      pointer.x += (pointer.tx - pointer.x) * 0.14
      pointer.y += (pointer.ty - pointer.y) * 0.14
      pointer.on += (pointer.onT - pointer.on) * 0.08

      ctx.clearRect(0, 0, w, h)

      // Soft spotlight under the cursor
      if (pointer.on > 0.01) {
        const g = ctx.createRadialGradient(pointer.x, pointer.y, 0, pointer.x, pointer.y, 340)
        g.addColorStop(0, `rgba(${A}, ${0.2 * pointer.on})`)
        g.addColorStop(0.5, `rgba(${B}, ${0.06 * pointer.on})`)
        g.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.fillStyle = g
        ctx.fillRect(0, 0, w, h)
      }

      for (let i = 0; i < dots.length; i++) {
        const d = dots[i]
        let fx = 0, fy = 0, k = 0

        const px = d.x - pointer.x, py = d.y - pointer.y
        const pd = Math.sqrt(px * px + py * py)
        if (pd < RADIUS && pointer.on > 0.01) {
          const f = (1 - pd / RADIUS) * pointer.on
          k = f
          if (pd > 0.001) { fx += (px / pd) * f * PUSH; fy += (py / pd) * f * PUSH }
        }

        for (let j = 0; j < ripples.length; j++) {
          const rp = ripples[j]
          const rx = d.x - rp.x, ry = d.y - rp.y
          const rd = Math.sqrt(rx * rx + ry * ry) || 1
          const band = Math.abs(rp.r - rd)
          if (band < 46) {
            const f = (1 - band / 46) * rp.s
            fx += (rx / rd) * f * 14; fy += (ry / rd) * f * 14
            if (f > k) k = f
          }
        }

        // Spring each dot toward its target offset
        d.vx = (d.vx + (fx - d.dx) * 0.14) * 0.76
        d.vy = (d.vy + (fy - d.dy) * 0.14) * 0.76
        d.dx += d.vx; d.dy += d.vy

        // Gentle ambient shimmer so the field is alive without input
        const amb = Math.sin(d.x * 0.011 + t * 0.0011) * Math.cos(d.y * 0.014 - t * 0.0008)
        const alpha = 0.09 + amb * 0.04 + k * 0.85
        const size = 1.1 + k * 2

        if (k > 0.02) {
          const m = d.x / w
          ctx.fillStyle = `rgba(${A[0] + (B[0] - A[0]) * m | 0}, ${A[1] + (B[1] - A[1]) * m | 0}, ${A[2] + (B[2] - A[2]) * m | 0}, ${alpha})`
        } else {
          ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`
        }
        ctx.beginPath()
        ctx.arc(d.x + d.dx, d.y + d.dy, size, 0, Math.PI * 2)
        ctx.fill()
      }

      for (let j = ripples.length - 1; j >= 0; j--) {
        const rp = ripples[j]
        rp.r += 7
        rp.s *= 0.982
        if (rp.s < 0.03 || rp.r > Math.max(w, h) * 1.3) ripples.splice(j, 1)
      }
    }

    const loop = (t) => {
      if (t - lastPulse > PULSE_EVERY) { orbPulse(); lastPulse = t }
      draw(t)
      raf = requestAnimationFrame(loop)
    }
    const start = () => { if (!running && !reduce) { running = true; raf = requestAnimationFrame(loop) } }
    const stop = () => { running = false; cancelAnimationFrame(raf) }

    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)
    // Only animate while the hero is on screen
    const io = new IntersectionObserver(([entry]) => (entry.isIntersecting ? start() : stop()))
    io.observe(canvas)

    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('pointerdown', onDown, { passive: true })
    document.addEventListener('pointerleave', onLeave)

    return () => {
      stop()
      ro.disconnect()
      io.disconnect()
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerdown', onDown)
      document.removeEventListener('pointerleave', onLeave)
    }
  }, [])

  return <canvas className="hero__field" ref={ref} aria-hidden="true" />
}
