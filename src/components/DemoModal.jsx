import { useEffect, useRef } from 'react'
import { lenisRef } from '../lib/motion'
import LeadForm from './LeadForm'

export default function DemoModal({ open, service, onClose }) {
  const panel = useRef(null)
  const lastFocus = useRef(null)

  useEffect(() => {
    if (!open) return
    lastFocus.current = document.activeElement
    lenisRef.current?.stop()
    document.body.style.overflow = 'hidden'
    const t = setTimeout(() => panel.current?.querySelector('input:not([type=hidden]):not(.lead-form__honey)')?.focus(), 60)

    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
      // Keep keyboard focus inside the dialog
      if (e.key === 'Tab') {
        const els = [...panel.current.querySelectorAll('button, [href], input:not(.lead-form__honey), select, textarea')].filter((el) => !el.disabled)
        const first = els[0], last = els.at(-1)
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      clearTimeout(t)
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      lenisRef.current?.start()
      lastFocus.current?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="modal" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal__panel" ref={panel} role="dialog" aria-modal="true" aria-labelledby="demo-title" data-lenis-prevent>
        <button className="modal__close" onClick={onClose} aria-label="Close">
          <svg viewBox="0 0 24 24" width="18" height="18"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
        </button>
        <p className="label">( Free 30-min demo )</p>
        <h2 id="demo-title" className="modal__title">Book a <em>demo</em></h2>
        <p className="modal__sub">See a live AI agent built around your use case. Pick a time that suits you and we’ll confirm within one business day.</p>
        <LeadForm variant="demo" defaultService={service} onDone={onClose} />
      </div>
    </div>
  )
}
