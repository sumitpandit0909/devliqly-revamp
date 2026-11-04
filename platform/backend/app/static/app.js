const $ = (id) => document.getElementById(id)
const views = ['login', 'setup', 'home']
let accessToken = null

function show(view) {
  views.forEach((name) => { $(name).hidden = name !== view })
}

function say(text, ok = false) {
  $('message').textContent = text || ''
  $('message').hidden = !text
  $('message').className = ok ? 'ok' : ''
}

async function post(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (response.ok) return response.status === 204 ? null : response.json()
  const data = await response.json().catch(() => ({}))
  // Validation errors arrive as a list, everything else as a sentence
  throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check what you entered and try again.')
}

async function openHome() {
  const response = await fetch('/api/me', { headers: { Authorization: `Bearer ${accessToken}` } })
  if (!response.ok) throw new Error('Session expired. Please log in again.')
  const me = await response.json()
  $('greeting').textContent = `Hello, ${me.full_name}`
  $('identity').textContent = me.is_operator ? `${me.email} · Devliqly operator` : me.email
  $('organizations').replaceChildren(...me.memberships.map(({ organization, role }) => {
    const row = document.createElement('li')
    const roleLabel = document.createElement('span')
    roleLabel.textContent = role
    row.append(organization.name, roleLabel)
    return row
  }))
  show('home')
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
  await openHome()
})

const setupToken = new URLSearchParams(location.hash.slice(1)).get('setup')

submitWith($('setup'), async (data) => {
  await post('/api/auth/set-password', { token: setupToken, password: data.get('password') })
  $('setup').reset()
  history.replaceState(null, '', location.pathname)
  show('login')
  say('Password saved. You can log in now.', true)
})

$('logout').addEventListener('click', async () => {
  await post('/api/auth/logout').catch(() => {})
  accessToken = null
  show('login')
})

async function start() {
  if (setupToken) return show('setup')
  try {
    const token = await post('/api/auth/refresh')
    accessToken = token.access_token
    await openHome()
  } catch {
    show('login')
  }
}

start()
