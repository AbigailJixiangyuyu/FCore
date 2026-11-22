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

    throw new Error('无法连接服务，请稍后重试。', { cause: error })
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
        .join('；')
    throw new Error(
      typeof detail === 'string'
        ? detail
        : `请求失败（HTTP ${response.status}），请稍后重试。`,
    )
  }

  if (!response.headers.get('content-type')?.includes('application/json')) {
    throw new Error('服务未返回有效的 JSON 数据。')
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
