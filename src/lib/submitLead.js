// Form submissions are delivered by FormSubmit (https://formsubmit.co) to the contact inbox.
// The first submission from a new domain triggers a one-time activation email to that inbox;
// nothing is delivered until the "Activate Form" link in it is clicked.
// This is the inbox the form was activated for, kept separate from the public CONTACT.email;
// changing it needs a fresh activation on every domain.
const ENDPOINT = 'https://formsubmit.co/ajax/contact.devliqly@gmail.com'

export async function submitLead(fields, { subject }) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 30000)
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
