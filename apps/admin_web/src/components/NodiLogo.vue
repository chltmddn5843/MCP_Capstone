<script setup>
// nodi 로고: 점 세 개가 이어져 'n' 아치로 들어가는 심볼(흩어진 사람·소프트웨어를 하나의 흐름으로 연결) + 워드마크.
// 심볼만 쓸 때(mark)는 라임 타일 위에 잉크색. 장식이므로 옆의 제품명 텍스트가 이름을 대신한다.
defineProps({ size: { type: Number, default: 32 }, wordmark: { type: Boolean, default: true } })
</script>

<template>
  <span class="nodi" aria-hidden="true">
    <span class="mark" :style="{ width: `${size}px`, height: `${size}px` }">
      <svg viewBox="0 0 48 48" :width="size * 0.78" :height="size * 0.78" fill="none" stroke="currentColor" stroke-linecap="round">
        <path d="M5 33.5h.01" stroke-width="5.5" />
        <path d="M12.5 32.5l3-.4M22 31l3-.6" stroke-width="5.5" />
        <path d="M31 33V20a7 7 0 0 1 14 0v13" stroke-width="5.5" />
      </svg>
    </span>
    <span v-if="wordmark" class="word" :style="{ fontSize: `${size * 0.72}px` }">nodi</span>
  </span>
</template>

<style scoped>
.nodi { display: inline-flex; align-items: center; gap: 10px; }
.mark { flex: none; display: grid; place-items: center; border-radius: 28%; background: var(--lime); color: var(--ink); }
.word { font-weight: 700; letter-spacing: -0.04em; line-height: 1; }
</style>
