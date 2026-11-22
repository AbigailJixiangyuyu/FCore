async function requestJson(path, { signal, method = 'GET', body } = {}) {
  let response

  try {
    response = await fetch(`/api${path}`, {
      signal,
      method,
      body,
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
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

export function postForm(path, body, options) {
  return requestJson(path, { ...options, method: 'POST', body })
}
