import assert from 'node:assert/strict'
import test from 'node:test'
import { renderReportMarkdown } from '../src/domain/reportMarkdown.js'

test('streamed Markdown resolves split emphasis, lists and citations', () => {
  const start = 'The membership changed.\n\n- **Historical'
  assert.doesNotMatch(renderReportMarkdown(start), /<strong>/)
  const html = renderReportMarkdown(start + ' pattern** 〔H01〕\n- Current 〔C02〕\n- Forecast 〔P01〕')
  assert.match(html, /<strong>Historical pattern<\/strong> 〔H01〕/)
  assert.equal(html.match(/<li>/g).length, 3)
  assert.match(renderReportMarkdown('### Findings\n\n1. 13 vertices.'), /<h3>Findings<\/h3>\s*<ol>/)
})

test('node IDs and model HTML remain text in formatted replies', () => {
  const html = renderReportMarkdown('**E025** and `**x**<tag>&` <img src=x> 〔C02〕')
  assert.match(html, /<strong>E025<\/strong>/)
  assert.match(html, /<code>\*\*x\*\*&lt;tag&gt;&amp;<\/code>/)
  assert.match(html, /&lt;img src=x&gt; 〔C02〕/)
})
