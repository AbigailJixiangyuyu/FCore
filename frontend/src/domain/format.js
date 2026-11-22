export function formatNumber(value, digits = 0) {
  return value == null
    ? '—'
    : value.toLocaleString('en-US', { maximumFractionDigits: digits })
}

export function formatCount(count, noun) {
  const label = count === 1 ? noun : `${noun}s`
  return `${formatNumber(count)} ${label}`
}
