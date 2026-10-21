import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import ko from 'element-plus/es/locale/lang/ko'
import App from './App.vue'
import router from './router'
import './style.css'

createApp(App).use(createPinia()).use(router).use(ElementPlus, { locale: ko }).mount('#app')
