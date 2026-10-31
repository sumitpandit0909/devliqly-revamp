import { useId, useState } from 'react'
import { CONTACT, SERVICES } from '../data'
import { submitLead } from '../lib/submitLead'

const TIME_SLOTS = ['10 AM – 12 PM', '12 PM – 3 PM', '3 PM – 6 PM', '6 PM – 8 PM']
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

const todayISO = () => {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 10)
}

const EMPTY = { name: '', email: '', phone: '', company: '', service: '', date: '', time: '', message: '' }

// Shared form for the inline contact section and the "Book a demo" dialog
export default function LeadForm({ variant = 'contact', defaultService = '', onDone }) {
  const isDemo = variant === 'demo'
  const uid = useId()
  const [values, setValues] = useState({ ...EMPTY, service: defaultService })
  const [errors, setErrors] = useState({})
  const [status, setStatus] = useState('idle') // idle | sending | success | error
  const [errorMsg, setErrorMsg] = useState('')

  const set = (k) => (e) => {
    setValues((v) => ({ ...v, [k]: e.target.value }))
    if (errors[k]) setErrors((er) => ({ ...er, [k]: undefined }))
  }

  const validate = () => {
    const er = {}
    if (values.name.trim().length < 2) er.name = 'Please enter your name.'
    if (!EMAIL_RE.test(values.email.trim())) er.email = 'Please enter a valid email address.'
    if (values.phone && values.phone.replace(/\D/g, '').length < 7) er.phone = 'Please enter a valid phone number.'
    if (isDemo && !values.phone.trim()) er.phone = 'We need a number to schedule the call.'
    if (!isDemo && values.message.trim().length < 10) er.message = 'Tell us a little more (at least 10 characters).'
    return er
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    const form = e.currentTarget
    // Honeypot: bots fill hidden fields, people don't
    if (form.elements._honey?.value) return

    const er = validate()
    setErrors(er)
    if (Object.keys(er).length) {
      form.querySelector(`[name="${Object.keys(er)[0]}"]`)?.focus()
      return
    }

    setStatus('sending')
    setErrorMsg('')
    const v = Object.fromEntries(Object.entries(values).map(([k, val]) => [k, val.trim()]))
    const fields = {
      'Request type': isDemo ? 'Demo booking' : 'General enquiry',
      name: v.name,
      email: v.email,
      Phone: v.phone || '—',
      Company: v.company || '—',
      Service: v.service || 'Not sure yet',
      ...(isDemo && { 'Preferred date': v.date || 'Flexible', 'Preferred time (IST)': v.time || 'Flexible' }),
      Message: v.message || '—',
    }
    try {
      await submitLead(fields, {
        subject: isDemo ? `New demo request: ${v.name}${v.company ? ` (${v.company})` : ''}` : `New enquiry: ${v.name}`,
      })
      setStatus('success')
      setValues({ ...EMPTY })
    } catch (err) {
      setStatus('error')
      setErrorMsg(err.name === 'AbortError' ? 'The request timed out.' : err.message)
    }
  }

  if (status === 'success') {
    return (
      <div className="lead-form__success" role="status">
        <span className="lead-form__check" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="28" height="28"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </span>
        <h3>{isDemo ? 'Demo request received!' : 'Message sent!'}</h3>
        <p>
          {isDemo
            ? 'Thanks! We’ll confirm your demo slot by email or phone within one business day.'
            : 'Thanks for reaching out. We’ll get back to you within 24 hours.'}
        </p>
        <div className="lead-form__success-actions">
          {onDone && <button type="button" className="btn" onClick={onDone}>Close</button>}
          <button type="button" className="btn btn--ghost" onClick={() => setStatus('idle')}>
            Send another
          </button>
        </div>
      </div>
    )
  }

  const field = (name, label, input, { required, full } = {}) => (
    <div className={`field ${full ? 'field--full' : ''} ${errors[name] ? 'has-error' : ''}`}>
      <label htmlFor={`${uid}-${name}`}>
        {label} {required && <span aria-hidden="true">*</span>}
      </label>
      {input}
      {errors[name] && <p className="field__error" id={`${uid}-${name}-err`}>{errors[name]}</p>}
    </div>
  )

  const common = (name) => ({
    id: `${uid}-${name}`,
    name,
    value: values[name],
    onChange: set(name),
    'aria-invalid': !!errors[name],
    'aria-describedby': errors[name] ? `${uid}-${name}-err` : undefined,
  })

  return (
    <form className={`lead-form lead-form--${variant}`} onSubmit={onSubmit} noValidate>
      <input type="text" name="_honey" className="lead-form__honey" tabIndex={-1} autoComplete="off" aria-hidden="true" />

      <div className="lead-form__grid">
        {field('name', 'Full name', <input {...common('name')} type="text" autoComplete="name" placeholder="Aarav Mehta" />, { required: true })}
        {field('email', 'Work email', <input {...common('email')} type="email" autoComplete="email" placeholder="you@company.com" />, { required: true })}
        {field('phone', 'Phone / WhatsApp', <input {...common('phone')} type="tel" autoComplete="tel" placeholder="+91 98765 43210" />, { required: isDemo })}
        {field('company', 'Company', <input {...common('company')} type="text" autoComplete="organization" placeholder="Acme Pvt Ltd" />)}
        {field('service', 'Interested in', (
          <select {...common('service')}>
            <option value="">Not sure yet</option>
            {SERVICES.map((s) => <option key={s.id} value={s.title}>{s.title}</option>)}
          </select>
        ), { full: true })}
        {isDemo && field('date', 'Preferred date', <input {...common('date')} type="date" min={todayISO()} />)}
        {isDemo && field('time', 'Preferred time (IST)', (
          <select {...common('time')}>
            <option value="">Flexible</option>
            {TIME_SLOTS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        ))}
        {field('message', isDemo ? 'Anything we should know?' : 'How can we help?', (
          <textarea
            {...common('message')}
            rows={isDemo ? 3 : 4}
            placeholder={isDemo ? 'e.g. We get ~300 support calls a day and want to automate order-status queries.' : 'Tell us about your business and what you’d like an AI agent to handle.'}
          />
        ), { required: !isDemo, full: true })}
      </div>

      {status === 'error' && (
        <div className="lead-form__alert" role="alert">
          <b>Sorry, your message couldn’t be sent.</b> {errorMsg && <span>({errorMsg})</span>}
          <br />
          Please try again, or reach us directly at{' '}
          <a href={`mailto:${CONTACT.email}`}>{CONTACT.email}</a> or on{' '}
          <a href={`https://wa.me/${CONTACT.phone.replace(/\D/g, '')}`} target="_blank" rel="noreferrer">WhatsApp</a>.
        </div>
      )}

      <div className="lead-form__foot">
        <button type="submit" className="btn" disabled={status === 'sending'}>
          {status === 'sending' ? (<><span className="spinner" aria-hidden="true" /> Sending…</>) : isDemo ? 'Request my demo' : 'Send message'}
        </button>
        <p className="lead-form__note">We reply within 24 hours. No spam, ever.</p>
      </div>
    </form>
  )
}
