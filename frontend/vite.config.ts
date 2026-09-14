import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Bind to 0.0.0.0 (not just localhost) so other devices on the same
    // organisation LAN can reach this dev server via the server
    // machine's LAN IP, e.g. http://192.168.1.50:5173. The proxy target
    // below stays "localhost:8000" on purpose - that's resolved by this
    // Vite process itself (which runs on the server machine, right next
    // to the backend), not by the browser making the request, so it
    // still correctly reaches the backend regardless of which LAN
    // device the browser is on.
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
