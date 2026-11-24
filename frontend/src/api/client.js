// getRandomValues also works on HTTP deployments outside localhost.
export function newRequestId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
}

let pageId
export function startDemoSession() {
  if (pageId) return
  pageId = newRequestId()
  window.addEventListener('pagehide', event => {
    if (!event.persisted)
      fetch('/api/demo-session', { method: 'DELETE', headers: { 'X-FCore-Session': pageId }, keepalive: true }).catch(() => {})
  })
}

async function request(path, { signal, method = 'GET', body, accept = 'application/json' } = {}) {
  let response

  try {
    response = await fetch(`/api${path}`, {
      signal,
      method,
      body,
      cache: 'no-store',
      headers: {
        Accept: accept,
        ...(pageId ? { 'X-FCore-Session': pageId } : {}),
        ...(typeof body === 'string' ? { 'Content-Type': 'application/json' } : {}),
      },
    })
  } catch (error) {
    if (error.name === 'AbortError') {
      throw error
    }

    throw new Error('Could not reach the service. Try again.', { cause: error })
  }

  if (!response.ok) {
    const payload = await response.json().catch(function () {
      return null
    })
    let detail = payload?.detail
    if (Array.isArray(detail))
      detail = detail
        .map(function (item) {
          return item.msg
        })
        .join(' | ')
    throw new Error(
      typeof detail === 'string'
        ? detail
        : `Request failed (HTTP ${response.status}). Try again.`,
    )
  }

  return response
}

async function requestJson(path, options) {
  const response = await request(path, options)
  if (!response.headers.get('content-type')?.includes('application/json')) {
    throw new Error('The service did not return valid JSON.')
  }

  return response.json()
}

export function getJson(path, options) {
  return requestJson(path, options)
}

export function postJson(path, body, options) {
  return requestJson(path, { ...options, method: 'POST', body: JSON.stringify(body) })
}

export async function* postJsonLines(path, body, { signal } = {}) {
  const response = await request(path, {
    signal, method: 'POST', body: JSON.stringify(body), accept: 'application/jsonl',
  })
  if (!response.body || !response.headers.get('content-type')?.includes('application/jsonl')) {
    throw new Error('The service did not return a report stream.')
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const lines = (buffer + value).split('\n')
      buffer = lines.pop()
      for (const line of lines) {
        if (line.trim()) yield JSON.parse(line)
      }
    }
    if (buffer.trim()) yield JSON.parse(buffer)
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('The report stream was interrupted. Try again.', { cause: error })
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}

export function postForm(path, body, options) {
  return requestJson(path, { ...options, method: 'POST', body })
}
