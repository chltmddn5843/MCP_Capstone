<script setup>
// 제품 로고 타일. 로고는 Simple Icons(CC0) SVG를 흰색으로 바꿔 src/assets/logos/에 둔다. 배경은 각 브랜드 공식 색.
// 로고가 없는 제품(후보 제품 등)은 제품명 첫 글자로 대신한다. 로고 옆에 제품명이 항상 함께 보이므로 장식으로 숨긴다.
import { computed } from 'vue'
import openai from '../assets/logos/openai.svg'
import claude from '../assets/logos/claude.svg'
import canva from '../assets/logos/canva.svg'
import acrobat from '../assets/logos/adobeacrobatreader.svg'

const props = defineProps({ toolId: { type: String, required: true }, name: { type: String, default: '' }, size: { type: Number, default: 32 } })
const LOGOS = {
  tool_chatgpt: { src: openai, bg: '#000000' },
  tool_claude: { src: claude, bg: '#D97757' },
  tool_canva: { src: canva, bg: '#00C4CC' },
  tool_adobe: { src: acrobat, bg: '#EC1C24' },
}
// 마법사에서 새로 등록한 제품은 id가 새로 생기므로 제품명으로도 찾는다
const BY_NAME = [[/chatgpt|openai/i, 'tool_chatgpt'], [/claude|anthropic/i, 'tool_claude'], [/canva/i, 'tool_canva'], [/acrobat|adobe/i, 'tool_adobe']]
const logo = computed(() => LOGOS[props.toolId] ?? LOGOS[BY_NAME.find(([re]) => re.test(props.name))?.[1]])
</script>

<template>
  <span class="logo-tile" :style="{ width: `${size}px`, height: `${size}px`, background: logo?.bg }" :class="{ mono: !logo }" aria-hidden="true">
    <img v-if="logo" :src="logo.src" alt="" :width="size * 0.58" :height="size * 0.58" />
    <span v-else :style="{ fontSize: `${size * 0.42}px` }">{{ name.slice(0, 1) }}</span>
  </span>
</template>

<style scoped>
.logo-tile { flex: none; display: inline-grid; place-items: center; border-radius: 22%; color: var(--white); font-weight: 700; }
.logo-tile.mono { background: var(--white); color: var(--ink); border: 1px solid var(--line-strong); }
</style>
