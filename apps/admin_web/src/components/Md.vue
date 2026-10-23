<script setup>
// 에이전트 답은 가벼운 마크다운(**굵게**, `코드`, - 목록, 1. 목록, ### 제목)을 섞어 온다. 그만큼만 그리고 나머지는 글자 그대로.
// HTML은 전부 이스케이프하므로 모델이 태그를 보내도 그대로 글자로 보인다.
import { computed } from 'vue'

const props = defineProps({ text: { type: String, default: '' } })
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>')
const html = computed(() => {
  const out = []
  let list = null
  const close = () => { if (list) { out.push(`</${list}>`); list = null } }
  for (const raw of props.text.split('\n')) {
    const line = raw.trimEnd()
    let m
    if ((m = line.match(/^\s*[-*•]\s+(.*)/))) { if (list !== 'ul') { close(); out.push('<ul>'); list = 'ul' } out.push(`<li>${inline(m[1])}</li>`) }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (list !== 'ol') { close(); out.push('<ol>'); list = 'ol' } out.push(`<li>${inline(m[1])}</li>`) }
    else if ((m = line.match(/^#{1,4}\s+(.*)/))) { close(); out.push(`<p><strong>${inline(m[1])}</strong></p>`) }
    else if (!line.trim()) close()
    else { close(); out.push(`<p>${inline(line)}</p>`) }
  }
  close()
  return out.join('')
})
</script>

<template>
  <div class="md" v-html="html" />
</template>

<style scoped>
.md { line-height: 1.65; font-size: 14px; }
.md :deep(p) { margin: 0 0 6px; }
.md :deep(p:last-child), .md :deep(ul:last-child), .md :deep(ol:last-child) { margin-bottom: 0; }
.md :deep(ul), .md :deep(ol) { margin: 0 0 6px; padding-left: 20px; }
.md :deep(li) { margin: 2px 0; }
.md :deep(code) { font-size: 12px; background: var(--track); padding: 1px 4px; border-radius: 4px; }
</style>
