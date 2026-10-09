import { test } from 'node:test'
import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('')
globalThis.window = dom.window
const { renderMarkdown } = await import('../src/utils/markdown.ts')

for (const attack of [
  '<script>alert(1)</script>',
  '<img src=x onerror=alert(1)>',
  '<svg onload=alert(1)><a href="javascript:alert(1)">x</a></svg>',
  '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
  '<a href="jav&#x61;script:alert(1)" onclick="alert(1)">x</a>',
  '<a href="java&#10;script:alert(1)">x</a>',
  '[x](javascript:alert%281%29)', '[x](data:text/html,test)',
  '[x](vbscript:alert)', '[x](//example.org)',
  '<form id=location><input name=href></form>',
  '<p style="background:url(javascript:alert(1))" onmouseover="alert(1)">x</p>',
]) {
  test(`removes active content: ${attack}`, () => {
    const root = dom.window.document.createElement('div')
    root.innerHTML = renderMarkdown(attack)
    assert.equal(root.querySelector('script,img,svg,iframe,form,input,style'), null)
    for (const el of root.querySelectorAll('*')) {
      for (const attr of el.attributes) {
        assert.ok(!/^on|^style$|^id$|^name$/.test(attr.name))
        if (attr.name === 'href') assert.match(attr.value, /^(https?:\/\/|mailto:|#)/i)
      }
    }
  })
}
test('keeps tables, escaped code, headings and safe links', () => {
  const html = renderMarkdown('# 标题\n\n|公司|收入|\n|---|---|\n|甲|100|\n\n```html\n<script>alert(1)</script>\n```\n\n[来源](https://example.org/report)')
  assert.match(html, /<table>/)
  assert.match(html, /<h1>标题<\/h1>/)
  assert.match(html, /&lt;script&gt;/)
  assert.match(html, /href="https:\/\/example.org\/report"/)
})
