import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt('commonmark', { html: false }).disable(['image', 'link', 'autolink'])

// Resolve IDs after parsing so punctuation in a vertex ID stays literal text.
markdown.core.ruler.push('report_node_labels', ({ tokens, env }) => {
  if (!env.nodeLabels) return
  for (const block of tokens) {
    for (const token of block.children ?? [block]) {
      if (['text', 'code_inline', 'code_block', 'fence'].includes(token.type)) {
        token.content = token.content.replace(/\bN\d{3,}\b/g, alias => env.nodeLabels[alias] ?? alias)
      }
    }
  }
})

export function renderReportMarkdown(content, nodeLabels) {
  return markdown.render(content, { nodeLabels })
}
