import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { VitePWA } from 'vite-plugin-pwa'

// O service worker só faz precache do shell estático. Sem runtimeCaching: as chamadas à API (e o /health do Boot) vão sempre à rede.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['apple-touch-icon.png'],
      manifest: {
        name: 'Studies',
        short_name: 'Studies',
        lang: 'pt-BR',
        description: 'Simulados e análises de estudo',
        display: 'standalone',
        start_url: '/',
        background_color: '#09090b',
        theme_color: '#09090b',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: { navigateFallback: '/index.html', globPatterns: ['**/*.{js,css,html,woff2,svg,png}'] },
    }),
  ],
  test: { environment: 'node' },
})
