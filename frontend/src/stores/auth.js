import { defineStore } from 'pinia'

// 토큰은 localStorage에 둔다 (MVP). 백엔드가 JWT로 바뀌어도 Authorization 헤더 형식은 같다.
export const useAuth = defineStore('auth', {
  state: () => ({ token: localStorage.getItem('token') || '', me: JSON.parse(localStorage.getItem('me') || 'null') }),
  getters: { role: s => s.me?.role || '', isAdmin: s => s.me?.role === 'admin', loggedIn: s => !!s.token },
  actions: {
    set(token, me) { this.token = token; this.me = me; localStorage.setItem('token', token); localStorage.setItem('me', JSON.stringify(me)) },
    logout() { this.token = ''; this.me = null; localStorage.removeItem('token'); localStorage.removeItem('me') },
  },
})
