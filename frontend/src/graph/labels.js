import { compareIds } from './layoutReference.js'

export function boxesOverlap(a, b, padding = 2) {
  return (
    a.left < b.right + padding &&
    a.right > b.left - padding &&
    a.top < b.bottom + padding &&
    a.bottom > b.top - padding
  )
}

export function measureNodeLabels(container) {
  const style = getComputedStyle(container)
  const height = Number.parseFloat(style.lineHeight)
  const padding = Number.parseFloat(style.getPropertyValue('--graph-label-inline-padding'))
  const context = document.createElement('canvas').getContext('2d')
  // Reserve the bold width so hovering does not displace the other labels.
  context.font = `700 ${style.fontSize} ${style.fontFamily}`
  const widths = new Map()
  return {
    height,
    widthFor(id) {
      if (!widths.has(id)) {
        widths.set(id, Math.ceil(context.measureText(id).width) + 2 * padding)
      }
      return widths.get(id)
    },
  }
}

export function placeNodeLabels(nodes, dimensions, enabled, metrics) {
  if (!enabled) return new Map()
  const labels = new Map()
  const occupied = [...(dimensions.reservedBoxes || [])]
  const visible = nodes.filter(function (node) {
    return (
      node.x >= 0 &&
      node.x <= dimensions.width &&
      node.y >= 0 &&
      node.y <= dimensions.height
    )
  })
  const ordered = [...visible].sort(function (a, b) {
    const priorityA = Number(!!(a.hovered || a.focused))
    const priorityB = Number(!!(b.hovered || b.focused))
    return (
      priorityB - priorityA || b.degree - a.degree || compareIds(a.id, b.id)
    )
  })
  const { height, widthFor } = metrics
  for (const node of ordered) {
    const width = widthFor(node.id)
    const gap = node.size + 5
    const candidates = [
      [gap, -height / 2],
      [-width - gap, -height / 2],
      [-width / 2, gap],
      [-width / 2, -gap - height],
      [gap, gap],
      [-width - gap, -gap - height],
      [gap, -gap - height],
      [-width - gap, gap],
    ]
    for (const [dx, dy] of candidates) {
      const box = {
        left: node.x + dx,
        top: node.y + dy,
        right: node.x + dx + width,
        bottom: node.y + dy + height,
      }
      if (
        box.left < 4 ||
        box.right > dimensions.width - 4 ||
        box.top < 38 ||
        box.bottom > dimensions.height - 4
      )
        continue
      if (
        occupied.some(function (other) {
          return boxesOverlap(box, other)
        })
      )
        continue
      if (
        visible.some(function (other) {
          return boxesOverlap(box, {
            left: other.x - other.size,
            right: other.x + other.size,
            top: other.y - other.size,
            bottom: other.y + other.size,
          })
        })
      )
        continue
      labels.set(node.id, box)
      occupied.push(box)
      break
    }
  }
  return labels
}
