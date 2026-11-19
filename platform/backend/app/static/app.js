const $ = (id) => document.getElementById(id)

let accessToken = null
let me = null
let orgId = null
let role = null

// All text goes in through textContent, so card contents can never become markup
function h(tag, props = {}, ...children) {
  const element = document.createElement(tag)
  for (const [name, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue
    if (name.startsWith('on')) element.addEventListener(name.slice(2), value)
    else if (name === 'class') element.className = value
    else if (name in element && name !== 'list') element[name] = value
    else element.setAttribute(name, value)
  }
  element.append(...children.flat().filter((child) => child !== null && child !== undefined && child !== false))
  return element
}

function toast(text, bad = false) {
  const box = $('toast')
  box.textContent = text
  box.className = bad ? 'bad' : ''
  box.hidden = false
  clearTimeout(toast.timer)
  toast.timer = setTimeout(() => { box.hidden = true }, 4000)
}

function say(text, ok = false) {
  $('message').textContent = text || ''
  $('message').hidden = !text
  $('message').className = ok ? 'ok' : ''
}

async function readError(response) {
  const data = await response.json().catch(() => ({}))
  // Validation errors arrive as a list, everything else as a sentence
  return typeof data.detail === 'string' ? data.detail : 'Please check what you entered and try again.'
}

async function post(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (response.ok) return response.status === 204 ? null : response.json()
  throw new Error(await readError(response))
}

let refreshing = null

async function refreshToken() {
  // Refresh tokens rotate and a replay ends the session, so parallel requests must share one refresh
  refreshing = refreshing || post('/api/auth/refresh').finally(() => { refreshing = null })
  accessToken = (await refreshing).access_token
}

async function send(path, { method = 'GET', body } = {}) {
  const attempt = () => {
    const headers = { Authorization: `Bearer ${accessToken}` }
    if (orgId) headers['X-Organization-Id'] = orgId
    if (body) headers['Content-Type'] = 'application/json'
    return fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined })
  }
  let response = await attempt()
  if (response.status === 401) {
    try {
      await refreshToken()
    } catch {
      showLogin('Your session ended. Please log in again.')
      throw new Error('Session ended')
    }
    response = await attempt()
  }
  return response
}

async function api(path, options) {
  const response = await send(path, options)
  if (!response.ok) throw new Error(await readError(response))
  return response.status === 204 ? null : response.json()
}

// Runs a change, shows what went wrong if it fails, and re-renders the screen
async function act(action, done) {
  try {
    await action()
    if (done) toast(done)
    await render()
  } catch (error) {
    toast(error.message, true)
  }
}

const canManage = () => role === 'owner' || role === 'manager'
const formatDate = (value) => (value ? new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '')
const tag = (text, kind) => (text ? h('span', { class: `tag ${kind || text}` }, text) : null)
const contactName = (row) => row.full_name || row.company || row.phone || row.email || 'Unknown'

function stat(label, value) {
  return h('div', { class: 'stat' }, h('strong', {}, String(value)), h('span', { class: 'muted small' }, label))
}

function bars(title, rows) {
  const top = Math.max(1, ...rows.map((row) => row.count))
  return h('section', { class: 'panel' }, h('h2', {}, title),
    rows.length ? rows.map((row) => h('div', { class: 'bar-row' },
      h('span', {}, row.label),
      h('b', {}, String(row.count)),
      h('div', { class: 'track' }, h('div', { class: 'fill', style: `width:${Math.round((row.count / top) * 100)}%` })),
    )) : h('p', { class: 'muted' }, 'Nothing yet.'))
}

function table(headers, rows) {
  return h('div', { class: 'table-wrap' }, h('table', {},
    h('thead', {}, h('tr', {}, headers.map((name) => h('th', { scope: 'col' }, name)))),
    h('tbody', {}, rows)))
}

function select(name, options, value, labelText) {
  return h('label', {}, labelText, h('select', { name },
    options.map(([optionValue, text]) => h('option', { value: optionValue, selected: optionValue === (value ?? '') }, text))))
}

function field(name, labelText, value = '', props = {}) {
  return h('label', {}, labelText, h('input', { name, value: value ?? '', ...props }))
}

function formValues(form) {
  return Object.fromEntries(new FormData(form).entries())
}

// Screens

async function dashboardView() {
  const events = await api('/api/org/events')
  const eventId = routeParams().get('event') || ''
  const board = await api(`/api/org/dashboard${eventId ? `?event_id=${eventId}` : ''}`)
  const eventPicker = h('select', {
    'aria-label': 'Event',
    onchange: (e) => { location.hash = e.target.value ? `#/dashboard?event=${e.target.value}` : '#/dashboard' },
  }, h('option', { value: '' }, 'All events'),
  events.map((event) => h('option', { value: event.id, selected: event.id === eventId }, event.name)))
  return [
    h('div', { class: 'head' }, h('h1', {}, 'Dashboard'), h('div', { class: 'row' }, eventPicker)),
    h('div', { class: 'stats' },
      stat('Leads', board.total),
      stat('Captured today', board.today),
      stat('Hot', board.hot),
      stat('Follow-ups due', board.follow_ups_due),
      stat('Waiting for review', board.waiting_review),
      stat('Cards this month', `${board.cards_this_month} / ${board.monthly_card_limit}`)),
    h('div', { class: 'columns' },
      bars('By event', board.by_event),
      bars('By rep', board.by_rep),
      bars('By status', board.by_status),
      bars('Follow-up messages', board.follow_ups)),
  ]
}

function routeParams() {
  return new URLSearchParams(location.hash.split('?')[1] || '')
}

function setRouteParams(params) {
  const base = location.hash.split('?')[0]
  const query = params.toString()
  location.hash = query ? `${base}?${query}` : base
}

const STATUSES = ['new', 'contacted', 'qualified', 'won', 'lost']
const INTERESTS = ['hot', 'warm', 'cold']
const PAGE_SIZE = 50

async function contactsView() {
  const params = routeParams()
  const offset = Number(params.get('offset') || 0)
  const query = new URLSearchParams()
  for (const name of ['q', 'event_id', 'status', 'interest', 'owner_id']) {
    if (params.get(name)) query.set(name, params.get(name))
  }
  const exportQuery = query.toString()
  query.set('limit', PAGE_SIZE)
  query.set('offset', offset)
  const [result, events, members] = await Promise.all([
    api(`/api/org/leads?${query}`),
    api('/api/org/events'),
    canManage() ? api('/api/org/members') : [],
  ])

  const applyFilters = (event) => {
    event.preventDefault()
    const next = new URLSearchParams()
    for (const [name, value] of Object.entries(formValues(event.target.form || event.target))) {
      if (value) next.set(name, value)
    }
    setRouteParams(next)
  }

  const download = async () => {
    const response = await send(`/api/org/leads/export.csv?${exportQuery}`)
    if (!response.ok) return toast(await readError(response), true)
    const url = URL.createObjectURL(await response.blob())
    const link = h('a', { href: url, download: 'leads.csv' })
    link.click()
    URL.revokeObjectURL(url)
  }

  const rows = result.items.map((row) => h('tr', {
    class: 'link',
    tabIndex: 0,
    onclick: () => { location.hash = `#/contacts/${row.id}` },
    onkeydown: (e) => { if (e.key === 'Enter') location.hash = `#/contacts/${row.id}` },
  },
  h('td', {}, h('strong', {}, contactName(row)), h('div', { class: 'muted small' }, row.job_title || '')),
  h('td', {}, row.company || ''),
  h('td', {}, h('div', {}, row.phone || ''), h('div', { class: 'muted small' }, row.email || '')),
  h('td', {}, row.event || ''),
  h('td', {}, row.owner || ''),
  h('td', {}, tag(row.status), ' ', tag(row.interest), ' ', row.needs_review ? tag('check', 'review') : null),
  h('td', { class: 'small muted' }, formatDate(row.created_at))))

  return [
    h('div', { class: 'head' },
      h('h1', {}, `Contacts (${result.total})`),
      canManage() ? h('button', { class: 'ghost', onclick: download }, 'Export CSV') : null),
    h('form', { class: 'filters', onsubmit: applyFilters, onchange: applyFilters },
      h('input', { type: 'search', name: 'q', placeholder: 'Search name, company, phone, email', value: params.get('q') || '', 'aria-label': 'Search' }),
      h('select', { name: 'event_id', 'aria-label': 'Event' }, h('option', { value: '' }, 'All events'),
        events.map((event) => h('option', { value: event.id, selected: event.id === params.get('event_id') }, event.name))),
      h('select', { name: 'status', 'aria-label': 'Status' }, h('option', { value: '' }, 'Any status'),
        STATUSES.map((value) => h('option', { value, selected: value === params.get('status') }, value))),
      h('select', { name: 'interest', 'aria-label': 'Interest' }, h('option', { value: '' }, 'Any interest'),
        INTERESTS.map((value) => h('option', { value, selected: value === params.get('interest') }, value))),
      canManage() ? h('select', { name: 'owner_id', 'aria-label': 'Rep' }, h('option', { value: '' }, 'All reps'),
        members.map((member) => h('option', { value: member.user_id, selected: member.user_id === params.get('owner_id') }, member.full_name))) : null),
    rows.length
      ? table(['Name', 'Company', 'Reach', 'Event', 'Rep', 'Status', 'Captured'], rows)
      : h('div', { class: 'panel empty' }, 'No contacts match. New ones appear here when reps send card photos on WhatsApp.'),
    result.total > PAGE_SIZE ? h('div', { class: 'pager' },
      h('button', { class: 'ghost small', disabled: offset === 0, onclick: () => { params.set('offset', Math.max(0, offset - PAGE_SIZE)); setRouteParams(params) } }, 'Previous'),
      h('span', { class: 'muted small' }, `${offset + 1}–${Math.min(offset + PAGE_SIZE, result.total)} of ${result.total}`),
      h('button', { class: 'ghost small', disabled: offset + PAGE_SIZE >= result.total, onclick: () => { params.set('offset', offset + PAGE_SIZE); setRouteParams(params) } }, 'Next')) : null,
  ]
}

function cardImage(cardId, side) {
  const image = h('img', { alt: `${side} of the business card` })
  send(`/api/org/cards/${cardId}/image?side=${side}`).then(async (response) => {
    if (response.ok) image.src = URL.createObjectURL(await response.blob())
    else image.alt = 'This photo could not be loaded'
  }).catch(() => {})
  return image
}

const ACTIVITY_LABELS = {
  captured: 'Card captured',
  rescanned: 'Card scanned again',
  note: 'Note',
  voice_note: 'Voice note',
  correction: 'Details corrected',
  status: 'Status changed',
  interest: 'Interest changed',
  follow_up_date: 'Follow-up date set',
  follow_up_planned: 'Follow-up written',
  follow_up_sent: 'Follow-up sent',
  back_added: 'Back of card added',
  whatsapp_consent: 'WhatsApp consent',
}

function followUpActions(followUp) {
  const url = `/api/org/follow-ups/${followUp.id}`
  const run = (path, done) => () => act(() => api(`${url}/${path}`, { method: 'POST' }), done)
  return h('div', { class: 'row' },
    followUp.status === 'draft' ? h('button', { class: 'small', onclick: run('approve', 'Follow-up approved') }, 'Approve and send') : null,
    followUp.status === 'failed' ? h('button', { class: 'small', onclick: run('retry', 'Trying again') }, 'Retry') : null,
    ['draft', 'scheduled', 'failed'].includes(followUp.status) ? h('button', { class: 'ghost small', onclick: run('cancel', 'Cancelled') }, 'Cancel') : null)
}

function followUpBlock(followUp) {
  return h('div', { class: 'panel' },
    h('div', { class: 'row' }, tag(followUp.status), tag(followUp.channel, 'channel'), h('span', { class: 'small muted' }, followUp.recipient)),
    followUp.subject ? h('p', {}, h('strong', {}, followUp.subject)) : null,
    followUp.body ? h('p', { class: 'preline small' }, followUp.body) : null,
    followUp.error ? h('p', { class: 'notice bad' }, followUp.error) : null,
    followUp.channel === 'whatsapp' && !followUp.body ? h('p', { class: 'small muted' }, 'Sends the approved WhatsApp template.') : null,
    followUpActions(followUp))
}

async function contactView(id) {
  const lead = await api(`/api/org/leads/${id}`)
  const save = (event) => {
    event.preventDefault()
    const values = formValues(event.target)
    const body = { status: values.status, interest: values.interest || null, next_step: values.next_step, follow_up_on: values.follow_up_on || null }
    for (const name of ['full_name', 'job_title', 'company', 'phone', 'email', 'website']) {
      if (values[name] && values[name] !== (lead[name] ?? '')) body[name] = values[name]
    }
    act(() => api(`/api/org/leads/${id}`, { method: 'PATCH', body }), 'Saved')
  }
  const addNote = (event) => {
    event.preventDefault()
    const { body } = formValues(event.target)
    act(() => api(`/api/org/leads/${id}/notes`, { method: 'POST', body: { body } }), 'Note added')
  }
  const erase = () => {
    // eslint-disable-next-line no-alert
    if (!confirm(`Permanently delete ${contactName(lead)}, including card photos and history? This can't be undone.`)) return
    api(`/api/org/contacts/${lead.contact_id}`, { method: 'DELETE' })
      .then(() => { toast('Contact deleted'); location.hash = '#/contacts' })
      .catch((error) => toast(error.message, true))
  }
  return [
    h('div', { class: 'head' },
      h('div', {},
        h('a', { href: '#/contacts', class: 'small' }, 'Back to contacts'),
        h('h1', {}, contactName(lead)),
        h('p', { class: 'muted small' }, [lead.event, lead.owner && `Rep: ${lead.owner}`].filter(Boolean).join(' · '))),
      lead.needs_review ? h('button', { class: 'ghost', onclick: () => act(() => api(`/api/org/leads/${id}`, { method: 'PATCH', body: { needs_review: false } }), 'Marked as checked') }, 'Mark as checked') : null),
    h('div', { class: 'split' },
      h('div', {},
        h('form', { class: 'panel', onsubmit: save },
          h('h2', {}, 'Details'),
          field('full_name', 'Name', lead.full_name),
          field('job_title', 'Title', lead.job_title),
          field('company', 'Company', lead.company),
          field('phone', 'Phone', lead.phone),
          lead.other_phones.length ? h('p', { class: 'small muted' }, `Other phones: ${lead.other_phones.join(', ')}`) : null,
          field('email', 'Email', lead.email),
          field('website', 'Website', lead.website),
          select('status', STATUSES.map((value) => [value, value]), lead.status, 'Status'),
          select('interest', [['', 'Not set'], ...INTERESTS.map((value) => [value, value])], lead.interest, 'Interest'),
          field('next_step', 'Next step', lead.next_step),
          field('follow_up_on', 'Follow up on', lead.follow_up_on, { type: 'date' }),
          h('button', { type: 'submit' }, 'Save')),
        h('section', { class: 'panel' },
          h('h2', {}, 'WhatsApp consent'),
          h('p', { class: 'small muted' }, 'A scanned card isn\'t agreement. Only turn this on if this person agreed to get WhatsApp messages.'),
          h('label', { class: 'check' },
            h('input', {
              type: 'checkbox',
              checked: lead.whatsapp_opt_in,
              onchange: (e) => act(() => api(`/api/org/leads/${id}`, { method: 'PATCH', body: { whatsapp_opt_in: e.target.checked } }), 'Saved'),
            }), 'Agreed to WhatsApp messages')),
        canManage() ? h('section', { class: 'panel' },
          h('h2', {}, 'Delete this person'),
          h('p', { class: 'small muted' }, 'For when someone asks to have their data removed. Deletes their details, photos, history and related chat messages.'),
          h('button', { class: 'danger', onclick: erase }, 'Delete permanently')) : null),
      h('div', {},
        lead.cards.some((card) => card.has_front || card.has_back) ? h('section', { class: 'panel' }, h('h2', {}, 'Card'),
          h('div', { class: 'card-photos' }, lead.cards.flatMap((card) => [
            card.has_front ? cardImage(card.id, 'front') : null,
            card.has_back ? cardImage(card.id, 'back') : null,
          ]))) : null,
        lead.cards.flatMap((card) => card.problems).length ? h('p', { class: 'notice' }, `Please check: ${lead.cards.flatMap((card) => card.problems).join('; ')}`) : null,
        lead.follow_ups.map(followUpBlock),
        h('form', { class: 'panel', onsubmit: addNote },
          h('h2', {}, 'Add a note'),
          h('textarea', { name: 'body', required: true, 'aria-label': 'Note' }),
          h('button', { type: 'submit' }, 'Add note')),
        h('section', { class: 'panel' }, h('h2', {}, 'Timeline'),
          h('ul', { class: 'timeline' }, lead.activities.map((activity) => h('li', {},
            h('span', { class: 'small muted' }, [ACTIVITY_LABELS[activity.kind] || activity.kind, activity.actor, formatDate(activity.created_at)].filter(Boolean).join(' · ')),
            activity.body ? h('p', {}, activity.body) : null,
            activity.details.transcript ? h('p', { class: 'small muted' }, `Said: ${activity.details.transcript}`) : null)))))),
  ]
}

async function reviewsView() {
  const cards = await api('/api/org/reviews')
  const form = (card) => {
    const reading = card.reading || {}
    const submit = (event) => {
      event.preventDefault()
      act(() => api(`/api/org/reviews/${card.id}/approve`, { method: 'POST', body: formValues(event.target) }), 'Saved as a contact')
    }
    return h('div', { class: 'panel' },
      h('div', { class: 'split' },
        h('div', {},
          card.has_front ? cardImage(card.id, 'front') : h('p', { class: 'muted' }, 'No photo.'),
          card.has_back ? cardImage(card.id, 'back') : null,
          h('p', { class: 'small muted' }, formatDate(card.created_at)),
          card.caption ? h('p', { class: 'small' }, `Rep's note: ${card.caption}`) : null,
          card.problems.length ? h('p', { class: 'notice' }, card.problems.join('; ')) : null),
        h('form', { onsubmit: submit },
          field('full_name', 'Name', reading.full_name),
          field('job_title', 'Title', reading.job_title),
          field('company', 'Company', reading.company),
          field('phone', 'Phone', (reading.phones || [])[0]),
          field('email', 'Email', (reading.emails || [])[0]),
          field('website', 'Website', reading.website),
          field('address', 'Address', reading.address),
          h('div', { class: 'row' },
            h('button', { type: 'submit' }, 'Save as contact'),
            h('button', { type: 'button', class: 'ghost', onclick: () => act(() => api(`/api/org/reviews/${card.id}/reject`, { method: 'POST' }), 'Dismissed') }, 'Dismiss')))))
  }
  return [
    h('div', { class: 'head' }, h('h1', {}, `Review queue (${cards.length})`)),
    cards.length ? cards.map(form) : h('div', { class: 'panel empty' }, 'Nothing is waiting for review.'),
  ]
}

// Connecting a customer's own WhatsApp number through Meta's Embedded Signup pop-up

let facebookReady = null

function loadFacebook(appId, version) {
  facebookReady = facebookReady || new Promise((resolve, reject) => {
    window.fbAsyncInit = () => {
      FB.init({ appId, autoLogAppEvents: false, xfbml: false, version })
      resolve()
    }
    document.body.append(h('script', {
      src: 'https://connect.facebook.net/en_US/sdk.js',
      async: true,
      crossOrigin: 'anonymous',
      onerror: () => {
        facebookReady = null
        reject(new Error('Couldn\'t load Facebook\'s sign-in. Check your connection or ad blocker and try again.'))
      },
    }))
  })
  return facebookReady
}

async function connectWhatsApp(setup) {
  await loadFacebook(setup.app_id, setup.graph_api_version)
  // Meta posts the chosen account and number to this window, separately from the login result
  let session = null
  const listen = (event) => {
    if (!/^https:\/\/(www|web)\.facebook\.com$/.test(event.origin)) return
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'WA_EMBEDDED_SIGNUP') session = data
    } catch { /* other Facebook messages aren't JSON */ }
  }
  window.addEventListener('message', listen)
  try {
    const code = await new Promise((resolve, reject) => FB.login((response) => {
      if (response.authResponse && response.authResponse.code) resolve(response.authResponse.code)
      else reject(new Error('Connecting was cancelled.'))
    }, {
      config_id: setup.config_id,
      response_type: 'code',
      override_default_response_type: true,
      // Offers to keep using the WhatsApp Business app on the same number (Coexistence)
      extras: { setup: {}, featureType: 'whatsapp_business_app_onboarding', sessionInfoVersion: '3' },
    }))
    for (let wait = 0; wait < 20 && !(session && session.data && session.data.waba_id); wait++) {
      await new Promise((resolve) => setTimeout(resolve, 150))
    }
    if (!session || session.event === 'CANCEL' || !session.data || !session.data.waba_id) {
      throw new Error('Meta didn\'t confirm which WhatsApp number was connected. Please try again.')
    }
    await api('/api/org/whatsapp/connect', {
      method: 'POST',
      body: { code, waba_id: session.data.waba_id, phone_number_id: session.data.phone_number_id || null },
    })
  } finally {
    window.removeEventListener('message', listen)
  }
}

const HISTORY_TEXT = {
  waiting: 'Waiting for WhatsApp to send your chats. Keep the WhatsApp Business app open on your phone.',
  done: 'Your chats are synced.',
  not_shared: 'You chose not to share past chats. New messages and follow-ups still work.',
  failed: 'The sync with the WhatsApp Business app didn\'t start. It has to start within 24 hours of connecting.',
}

function whatsappPanel(setup) {
  const number = setup.number
  if (!number) {
    return h('section', { class: 'panel', style: 'margin-top:16px' },
      h('h2', {}, 'Your WhatsApp number'),
      h('p', { class: 'small muted' }, 'Connect your company\'s WhatsApp number so follow-ups come from you. If the number is on the WhatsApp Business app, you can keep using the app as before.'),
      setup.can_connect
        ? h('button', { onclick: () => act(() => connectWhatsApp(setup), 'WhatsApp number connected') }, 'Connect WhatsApp')
        : h('p', { class: 'small muted' }, 'Connecting your own number isn\'t available yet. Until then, follow-ups go from Devliqly\'s number.'))
  }
  const history = number.history_status === 'syncing'
    ? `Syncing your chats: ${number.history_progress || 0}%`
    : HISTORY_TEXT[number.history_status]
  const disconnect = () => {
    if (!confirm('Disconnect this number? Follow-ups will go from Devliqly\'s number instead.')) return
    act(() => api('/api/org/whatsapp', { method: 'DELETE' }), 'WhatsApp number disconnected')
  }
  return h('section', { class: 'panel', style: 'margin-top:16px' },
    h('h2', {}, 'Your WhatsApp number'),
    h('p', {}, h('strong', {}, number.display_phone || 'Connected number'), ' ', number.verified_name ? `(${number.verified_name})` : '', ' ', tag(number.status === 'connected' ? 'connected' : 'disconnected')),
    number.on_business_app ? h('p', { class: 'small muted' }, 'Also on the WhatsApp Business app. Keep chatting there as usual; messages you type in the app stay free.') : null,
    number.status !== 'connected' ? h('p', { class: 'small', style: 'color:var(--error)' }, `Disconnected${number.disconnect_reason ? `: ${number.disconnect_reason}` : ''}. Follow-ups go from Devliqly's number until you connect again.`) : null,
    history ? h('p', { class: 'small muted' }, history) : null,
    h('div', { class: 'row' },
      number.history_status === 'failed' && number.status === 'connected'
        ? h('button', { class: 'ghost small', onclick: () => act(() => api('/api/org/whatsapp/retry-sync', { method: 'POST' }), 'Sync started') }, 'Try the sync again')
        : null,
      number.status !== 'connected' && setup.can_connect
        ? h('button', { class: 'small', onclick: () => act(() => connectWhatsApp(setup), 'WhatsApp number connected') }, 'Connect again')
        : null,
      h('button', { class: 'ghost small', onclick: disconnect }, 'Disconnect')),
    number.on_business_app ? h('p', { class: 'small muted' }, 'To disconnect completely, also open the WhatsApp Business app: Settings → Account → Business Platform.') : null)
}

function templatePicker(settings, templates) {
  if (!templates.length) return field('whatsapp_template', 'Approved template name', settings.whatsapp_template)
  const choose = (event) => {
    const chosen = templates.find((template) => template.name === event.target.value)
    const language = event.target.form.elements.whatsapp_language
    if (chosen && language) language.value = chosen.language
  }
  return h('label', {}, 'Approved template', h('select', { name: 'whatsapp_template', onchange: choose },
    h('option', { value: '' }, 'Choose a template'),
    templates.map((template) => h('option', { value: template.name, selected: template.name === settings.whatsapp_template },
      `${template.name} (${template.language}, ${template.category.toLowerCase()})`))))
}

async function followUpsView() {
  const status = routeParams().get('status') || ''
  const rows = await api(`/api/org/follow-ups${status ? `?status=${status}` : ''}`)
  const settings = canManage() ? await api('/api/org/follow-up-settings') : null
  const optOuts = canManage() ? await api('/api/org/opt-outs') : []
  const whatsapp = canManage() ? await api('/api/org/whatsapp') : null
  const connected = whatsapp && whatsapp.number && whatsapp.number.status === 'connected'
  // Approved templates from the customer's own number, so nobody has to type a name exactly
  const templates = connected ? await api('/api/org/whatsapp/templates').catch(() => []) : []

  const saveSettings = (event) => {
    event.preventDefault()
    const values = formValues(event.target)
    const body = {
      email_enabled: 'email_enabled' in values,
      auto_send: 'auto_send' in values,
      delay_minutes: Number(values.delay_minutes || 0),
      sender_name: values.sender_name || null,
      reply_to: values.reply_to || null,
      email_subject: values.email_subject,
      email_body: values.email_body,
      whatsapp_enabled: 'whatsapp_enabled' in values,
      whatsapp_template: values.whatsapp_template || null,
      whatsapp_language: values.whatsapp_language || 'en',
      whatsapp_consent_at_capture: 'whatsapp_consent_at_capture' in values,
    }
    act(() => api('/api/org/follow-up-settings', { method: 'PUT', body }), 'Settings saved')
  }
  const addOptOut = (event) => {
    event.preventDefault()
    act(() => api('/api/org/opt-outs', { method: 'POST', body: formValues(event.target) }), 'Added to the opt-out list')
  }

  return [
    h('div', { class: 'head' }, h('h1', {}, 'Follow-ups'),
      h('select', {
        'aria-label': 'Status',
        onchange: (e) => setRouteParams(new URLSearchParams(e.target.value ? { status: e.target.value } : {})),
      }, h('option', { value: '' }, 'All'), ['draft', 'scheduled', 'sent', 'failed', 'blocked', 'cancelled'].map((value) => h('option', { value, selected: value === status }, value)))),
    rows.length ? table(['To', 'Message', 'Status', ''], rows.map((row) => h('tr', {},
      h('td', {}, h('a', { href: `#/contacts/${row.lead_id}` }, row.contact_name || row.recipient), h('div', { class: 'small muted' }, row.recipient)),
      h('td', {}, tag(row.channel, 'channel'), ' ', row.subject || 'WhatsApp template', row.error ? h('div', { class: 'small', style: 'color:var(--error)' }, row.error) : null),
      h('td', {}, tag(row.status)),
      h('td', {}, followUpActions(row))))) : h('div', { class: 'panel empty' }, 'No follow-ups here. They appear once follow-ups are switched on below.'),
    whatsapp ? whatsappPanel(whatsapp) : null,
    settings ? h('div', { class: 'split', style: 'margin-top:16px' },
      h('form', { class: 'panel', onsubmit: saveSettings },
        h('h2', {}, 'Settings'),
        h('p', { class: 'small muted' }, 'You can use {first_name}, {full_name}, {company}, {rep_name}, {organization} and {event} in the subject and message.'),
        h('label', { class: 'check' }, h('input', { type: 'checkbox', name: 'email_enabled', checked: settings.email_enabled }), 'Write follow-up emails'),
        field('email_subject', 'Subject', settings.email_subject),
        h('label', {}, 'Message', h('textarea', { name: 'email_body', value: settings.email_body })),
        field('sender_name', 'Sender name', settings.sender_name),
        field('reply_to', 'Replies go to', settings.reply_to, { type: 'email' }),
        h('label', { class: 'check' }, h('input', { type: 'checkbox', name: 'auto_send', checked: settings.auto_send }), 'Send automatically (untick to approve each one first)'),
        field('delay_minutes', 'Wait before sending (minutes)', settings.delay_minutes, { type: 'number', min: 0 }),
        h('label', { class: 'check' }, h('input', { type: 'checkbox', name: 'whatsapp_enabled', checked: settings.whatsapp_enabled }), 'WhatsApp follow-ups (only to people who agreed)'),
        templatePicker(settings, templates),
        field('whatsapp_language', 'Template language', settings.whatsapp_language),
        h('label', { class: 'check' }, h('input', { type: 'checkbox', name: 'whatsapp_consent_at_capture', checked: settings.whatsapp_consent_at_capture }), 'Our reps ask every visitor for permission to message them on WhatsApp'),
        h('p', { class: 'small muted' }, 'When ticked, each new card counts as agreed, so you don\'t tick every lead. Only tick this if your reps really ask: WhatsApp requires permission, and messaging people who didn\'t agree can get your number restricted. You can still untick a single lead.'),
        h('button', { type: 'submit' }, 'Save settings')),
      h('section', { class: 'panel' },
        h('h2', {}, 'Opt-out list'),
        h('form', { onsubmit: addOptOut, style: 'margin-bottom:12px' },
          select('channel', [['email', 'Email'], ['whatsapp', 'WhatsApp']], 'email', 'Channel'),
          field('address', 'Email or phone', '', { required: true }),
          h('button', { type: 'submit', class: 'ghost' }, 'Add')),
        optOuts.length ? h('ul', { class: 'timeline' }, optOuts.map((row) => h('li', {}, row.address, h('div', { class: 'small muted' }, `${row.channel} · ${formatDate(row.created_at)}`))))
          : h('p', { class: 'muted small' }, 'Nobody has opted out.'))) : null,
  ]
}

async function eventsView() {
  const events = await api('/api/org/events')
  const create = (event) => {
    event.preventDefault()
    const values = formValues(event.target)
    const body = { name: values.name, venue: values.venue || null, starts_on: values.starts_on || null, ends_on: values.ends_on || null }
    act(() => api('/api/org/events', { method: 'POST', body }), 'Event added')
  }
  return [
    h('div', { class: 'head' }, h('h1', {}, 'Events')),
    canManage() ? h('form', { class: 'panel', onsubmit: create },
      h('h2', {}, 'Add an event'),
      field('name', 'Name', '', { required: true }),
      field('venue', 'Venue'),
      field('starts_on', 'Starts', '', { type: 'date' }),
      field('ends_on', 'Ends', '', { type: 'date' }),
      h('button', { type: 'submit' }, 'Add event')) : null,
    events.length ? table(['Event', 'Venue', 'Dates', '', ''], events.map((event) => h('tr', {},
      h('td', {}, h('strong', {}, event.name)),
      h('td', {}, event.venue || ''),
      h('td', { class: 'small' }, [event.starts_on, event.ends_on].filter(Boolean).join(' to ')),
      h('td', {}, h('a', { href: `#/contacts?event_id=${event.id}` }, 'Leads')),
      h('td', {}, canManage() ? h('button', {
        class: 'ghost small',
        onclick: () => act(() => api(`/api/org/events/${event.id}`, { method: 'PATCH', body: { is_active: !event.is_active } })),
      }, event.is_active ? 'Close' : 'Reopen') : null)))) : h('div', { class: 'panel empty' }, 'No events yet.'),
  ]
}

async function teamView() {
  const members = await api('/api/org/members')
  const add = (event) => {
    event.preventDefault()
    const values = formValues(event.target)
    const body = { full_name: values.full_name, role: values.role, phone: values.phone || null, email: values.email || null }
    act(async () => {
      const created = await api('/api/org/members', { method: 'POST', body })
      sessionStorage.setItem('setupLink', created.setup_url || '')
    }, 'Team member added')
  }
  const setupLink = sessionStorage.getItem('setupLink')
  sessionStorage.removeItem('setupLink')
  return [
    h('div', { class: 'head' }, h('h1', {}, 'Team')),
    setupLink ? h('div', { class: 'panel' },
      h('h2', {}, 'Send them this link to choose a password'),
      h('code', { class: 'copy' }, setupLink),
      h('p', { class: 'small muted' }, 'It works once and isn\'t shown again.')) : null,
    canManage() ? h('form', { class: 'panel', onsubmit: add },
      h('h2', {}, 'Add someone'),
      field('full_name', 'Name', '', { required: true }),
      field('phone', 'WhatsApp number (reps need this)', ''),
      field('email', 'Email (needed to log in to this CRM)', '', { type: 'email' }),
      select('role', [['rep', 'Rep'], ['manager', 'Manager'], ['owner', 'Owner']], 'rep', 'Role'),
      h('button', { type: 'submit' }, 'Add')) : null,
    table(['Name', 'Phone', 'Email', 'Role', ''], members.map((member) => h('tr', {},
      h('td', {}, h('strong', {}, member.full_name), member.is_active ? null : h('div', { class: 'small muted' }, 'Removed')),
      h('td', {}, member.phone || ''),
      h('td', {}, member.email || ''),
      h('td', {}, member.role),
      h('td', {}, canManage() ? h('button', {
        class: 'ghost small',
        onclick: () => act(() => api(`/api/org/members/${member.id}`, { method: 'PATCH', body: { is_active: !member.is_active } })),
      }, member.is_active ? 'Remove' : 'Restore') : null)))),
  ]
}

async function chatsView(id) {
  const conversations = await api('/api/org/conversations')
  const messages = id ? await api(`/api/org/conversations/${id}/messages`) : null
  return [
    h('div', { class: 'head' }, h('h1', {}, 'WhatsApp chats')),
    h('div', { class: 'split' },
      conversations.length ? table(['Rep', 'Last message'], conversations.map((conversation) => h('tr', {
        class: 'link',
        tabIndex: 0,
        onclick: () => { location.hash = `#/chats/${conversation.id}` },
        onkeydown: (e) => { if (e.key === 'Enter') location.hash = `#/chats/${conversation.id}` },
      }, h('td', {}, conversation.rep_name, h('div', { class: 'small muted' }, conversation.rep_phone || '')),
      h('td', { class: 'small muted' }, formatDate(conversation.last_inbound_at))))) : h('div', { class: 'panel empty' }, 'No chats yet.'),
      messages ? h('section', { class: 'panel' }, messages.map((message) => h('div', { class: `bubble ${message.direction === 'out' ? 'out' : ''}` },
        h('div', { class: 'preline' }, message.body || `(${message.kind})`),
        h('div', { class: 'small muted' }, [formatDate(message.created_at), message.status === 'failed' ? `Failed: ${message.error}` : null].filter(Boolean).join(' · '))))) : null),
  ]
}

async function staffView() {
  const [overview, dead] = await Promise.all([api('/api/operator/overview'), api('/api/operator/jobs/dead')])
  const create = (event) => {
    event.preventDefault()
    const values = formValues(event.target)
    act(async () => {
      const created = await api('/api/operator/organizations', {
        method: 'POST',
        body: { name: values.name, owner: { full_name: values.owner_name, email: values.owner_email } },
      })
      sessionStorage.setItem('setupLink', created.owner_setup_url)
    }, 'Customer added')
  }
  const edit = (event, id) => {
    event.preventDefault()
    const values = formValues(event.target)
    const body = { plan: values.plan, monthly_card_limit: Number(values.monthly_card_limit), seat_limit: Number(values.seat_limit) }
    act(() => api(`/api/operator/organizations/${id}`, { method: 'PATCH', body }), 'Plan saved')
  }
  const setupLink = sessionStorage.getItem('setupLink')
  sessionStorage.removeItem('setupLink')
  const totalCost = overview.organizations.reduce((sum, org) => sum + org.ai_cost_usd_this_month, 0)
  return [
    h('div', { class: 'head' }, h('h1', {}, 'Staff')),
    h('div', { class: 'stats' },
      stat('Customers', overview.organizations.length),
      stat('Estimated AI cost this month', `$${totalCost.toFixed(2)}`),
      stat('Failed AI calls this month', overview.ai_calls_failed_this_month),
      stat('Jobs waiting', overview.jobs.pending + overview.jobs.running),
      stat('Failed jobs', overview.jobs.dead)),
    setupLink ? h('div', { class: 'panel' }, h('h2', {}, 'Send this to the owner to choose a password'), h('code', { class: 'copy' }, setupLink)) : null,
    table(['Customer', 'Cards this month', 'AI calls', 'AI cost', 'Plan'], overview.organizations.map((org) => h('tr', {},
      h('td', {}, h('strong', {}, org.name), org.is_active ? null : h('div', { class: 'small muted' }, 'Inactive')),
      h('td', {}, `${org.cards_this_month} / ${org.monthly_card_limit}`),
      h('td', {}, String(org.ai_calls_this_month)),
      h('td', {}, `$${org.ai_cost_usd_this_month.toFixed(2)}`),
      h('td', {}, h('form', { class: 'row', onsubmit: (event) => edit(event, org.id) },
        h('input', { name: 'plan', value: org.plan, 'aria-label': 'Plan', style: 'width:90px' }),
        h('input', { name: 'monthly_card_limit', type: 'number', min: 1, value: org.monthly_card_limit, 'aria-label': 'Monthly cards', style: 'width:90px' }),
        h('input', { name: 'seat_limit', type: 'number', min: 1, value: org.seat_limit, 'aria-label': 'Seats', style: 'width:70px' }),
        h('button', { class: 'ghost small', type: 'submit' }, 'Save')))))),
    h('form', { class: 'panel', onsubmit: create, style: 'margin-top:16px' },
      h('h2', {}, 'Add a customer'),
      field('name', 'Company', '', { required: true }),
      field('owner_name', 'Owner\'s name', '', { required: true }),
      field('owner_email', 'Owner\'s email', '', { type: 'email', required: true }),
      h('button', { type: 'submit' }, 'Add customer')),
    h('section', { class: 'panel' }, h('h2', {}, `Failed jobs (${dead.length})`),
      dead.length ? table(['Job', 'Error', ''], dead.map((job) => h('tr', {},
        h('td', {}, job.kind, h('div', { class: 'small muted' }, `#${job.seq} · ${formatDate(job.finished_at)}`)),
        h('td', { class: 'small' }, job.last_error || ''),
        h('td', {}, h('button', { class: 'ghost small', onclick: () => act(() => api(`/api/operator/jobs/${job.seq}/retry`, { method: 'POST' }), 'Queued again') }, 'Retry')))))
        : h('p', { class: 'muted small' }, 'None.')),
  ]
}

// Navigation

function routes() {
  const org = orgId ? [
    ['dashboard', 'Dashboard'],
    ['contacts', 'Contacts'],
    ['review', 'Review queue'],
    ['follow-ups', 'Follow-ups'],
    ['events', 'Events'],
    ['team', 'Team'],
    ['chats', 'Chats'],
  ] : []
  return me.is_operator ? [...org, ['staff', 'Staff']] : org
}

const VIEWS = {
  dashboard: dashboardView,
  contacts: contactsView,
  review: reviewsView,
  'follow-ups': followUpsView,
  events: eventsView,
  team: teamView,
  chats: chatsView,
  staff: staffView,
}

let renderCount = 0

async function render() {
  const available = routes()
  if (!available.length) {
    $('view').replaceChildren(h('div', { class: 'panel empty' }, 'Your account isn\'t part of a company yet.'))
    return
  }
  const [name, id] = location.hash.replace(/^#\/?/, '').split('?')[0].split('/')
  const route = available.some(([key]) => key === name) ? name : available[0][0]
  $('nav').replaceChildren(...available.map(([key, label]) => h('a', {
    href: `#/${key}`,
    'aria-current': key === route ? 'page' : undefined,
  }, label)))
  const current = ++renderCount
  try {
    const content = route === 'contacts' && id ? await contactView(id) : await VIEWS[route](id)
    // A slower, older screen mustn't replace the one the person has since opened
    if (current === renderCount) $('view').replaceChildren(...content.flat().filter(Boolean))
  } catch (error) {
    if (current === renderCount) $('view').replaceChildren(h('div', { class: 'panel notice bad' }, error.message))
  }
}

function showLogin(text) {
  accessToken = null
  // Customer data shouldn't stay in the page after logging out
  $('view').replaceChildren()
  $('shell').hidden = true
  $('auth').hidden = false
  $('login').hidden = false
  $('setup').hidden = true
  say(text)
}

async function openApp() {
  me = await api('/api/me')
  const active = me.memberships.filter((membership) => membership.organization.is_active)
  const saved = sessionStorage.getItem('organization')
  const chosen = active.find((membership) => membership.organization.id === saved) || active[0]
  orgId = chosen ? chosen.organization.id : null
  role = chosen ? chosen.role : null
  $('org-picker').hidden = active.length < 2
  $('org-select').replaceChildren(...active.map((membership) => h('option', {
    value: membership.organization.id,
    selected: membership.organization.id === orgId,
  }, membership.organization.name)))
  $('identity').textContent = me.is_operator ? `${me.email} · Staff` : `${me.email}${role ? ` · ${role}` : ''}`
  $('auth').hidden = true
  $('shell').hidden = false
  await render()
}

function submitWith(form, handler) {
  form.addEventListener('submit', async (event) => {
    event.preventDefault()
    const button = form.querySelector('button')
    button.disabled = true
    say('')
    try {
      await handler(new FormData(form))
    } catch (error) {
      say(error.message)
    } finally {
      button.disabled = false
    }
  })
}

submitWith($('login'), async (data) => {
  const token = await post('/api/auth/login', { email: data.get('email'), password: data.get('password') })
  accessToken = token.access_token
  $('login').reset()
  await openApp()
})

const setupToken = new URLSearchParams(location.hash.slice(1)).get('setup')

submitWith($('setup'), async (data) => {
  await post('/api/auth/set-password', { token: setupToken, password: data.get('password') })
  $('setup').reset()
  history.replaceState(null, '', location.pathname)
  showLogin('')
  say('Password saved. You can log in now.', true)
})

$('logout').addEventListener('click', async () => {
  await post('/api/auth/logout').catch(() => {})
  showLogin('')
})

$('org-select').addEventListener('change', (event) => {
  sessionStorage.setItem('organization', event.target.value)
  location.hash = '#/dashboard'
  openApp()
})

window.addEventListener('hashchange', () => { if (accessToken) render() })

async function start() {
  if (setupToken) {
    $('auth').hidden = false
    $('setup').hidden = false
    return
  }
  try {
    const token = await post('/api/auth/refresh')
    accessToken = token.access_token
    await openApp()
  } catch {
    showLogin('')
  }
}

start()
