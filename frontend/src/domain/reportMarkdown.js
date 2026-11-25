import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt('commonmark', { html: false }).disable(['image', 'link', 'autolink'])

export function renderReportMarkdown(content) {
  return markdown.render(content)
}
