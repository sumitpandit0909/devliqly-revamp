import { CONTACT } from '../data'

// Form submissions are delivered by FormSubmit (https://formsubmit.co) to the contact inbox.
// The first submission from a new domain triggers a one-time activation email to that inbox;
// nothing is delivered until the "Activate Form" link in it is clicked.
const ENDPOINT = `https://formsubmit.co/ajax/${CONTACT.email}`

export async function submitLead(fields, { subject }) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 15000)
  try {
    const res = await fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        ...fields,
        _subject: subject,
        _template: 'table',
        _captcha: 'false',
        page: window.location.href,
      }),
      signal: controller.signal,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok || String(data.success) !== 'true') {
      throw new Error(data.message || `Request failed (${res.status})`)
    }
    return data
  } finally {
    clearTimeout(timer)
  }
}
