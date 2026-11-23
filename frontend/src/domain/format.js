export function formatNumber(value, digits = 0) {
  return value == null
    ? '—'
    : value.toLocaleString('en-US', { maximumFractionDigits: digits })
}

export function formatCount(count, noun, plural = `${noun}s`) {
  const label = count === 1 ? noun : plural
  return `${formatNumber(count)} ${label}`
}
