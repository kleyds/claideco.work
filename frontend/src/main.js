import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Home from './views/Home.vue'
import Products from './views/Products.vue'
import PesoBooks from './views/PesoBooks.vue'
import Docs from './views/Docs.vue'
import About from './views/About.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/products', name: 'products', component: Products },
    { path: '/pesobooks', name: 'pesobooks', component: PesoBooks },
    { path: '/docs', name: 'docs', component: Docs },
    { path: '/about', name: 'about', component: About },
  ],
  scrollBehavior(to) {
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0 }
  },
})

createApp(App).use(router).mount('#app')
