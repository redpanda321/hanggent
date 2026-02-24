/**
 * Vite configuration for Web mode (no Electron)
 * 
 * This configuration runs the Hanggent frontend as a pure web application,
 * connecting to backend (port 5001) and server (port 3001) via HTTP proxy.
 * 
 * Usage:
 *   npm run dev:web     - Start development server
 *   npm run build:web   - Build for production
 */

import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const isServe = command === 'serve'
  const isBuild = command === 'build'
  const sourcemap = isServe
  const env = loadEnv(mode, process.cwd(), '')
  
  // Default URLs for backend services
  const backendUrl = env.VITE_BACKEND_URL || 'http://localhost:5001'
  const serverUrl = env.VITE_PROXY_URL || 'http://localhost:3001'
  
  console.log(`[Web Mode] Backend URL: ${backendUrl}`)
  console.log(`[Web Mode] Server URL: ${serverUrl}`)
  
  return {
    // Define global constants
    define: {
      // Mark as web mode for runtime detection
      'import.meta.env.VITE_APP_MODE': JSON.stringify('web'),
    },
    
    resolve: {
      alias: {
        '@': path.join(__dirname, 'src'),
      },
    },
    
    optimizeDeps: {
      include: [
        'use-sync-external-store',
        'use-sync-external-store/shim',
        'use-sync-external-store/shim/index.js',
        'yup',
        'tiny-case',
      ],
      force: true,
    },
    
    plugins: [
      react(),
      // No Electron plugin in web mode
    ],
    
    server: {
      port: 5173,
      open: true,
      
      // Proxy configuration for API requests
      proxy: {
        // Backend API (hanggent/backend on port 5001)
        '/api/backend': {
          target: backendUrl,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/backend/, ''),
          configure: (proxy, options) => {
            proxy.on('error', (err, req, res) => {
              console.error('[Proxy Error - Backend]', err.message)
            })
            proxy.on('proxyReq', (proxyReq, req, res) => {
              console.log(`[Proxy] ${req.method} ${req.url} -> ${backendUrl}`)
            })
          },
        },
        
        // Server API (hanggent/server on port 3001)
        '/api': {
          target: serverUrl,
          changeOrigin: true,
          ws: true,
          configure: (proxy, options) => {
            proxy.on('error', (err, req, res) => {
              console.error('[Proxy Error - Server]', err.message)
            })
            proxy.on('proxyReq', (proxyReq, req, res) => {
              console.log(`[Proxy] ${req.method} ${req.url} -> ${serverUrl}`)
            })
          },
        },

        // Payment endpoints (used by Pricing/Billing pages)
        '/payment': {
          target: serverUrl,
          changeOrigin: true,
          configure: (proxy, options) => {
            proxy.on('error', (err, req, res) => {
              console.error('[Proxy Error - Payment]', err.message)
            })
            proxy.on('proxyReq', (proxyReq, req, res) => {
              console.log(`[Proxy] ${req.method} ${req.url} -> ${serverUrl}`)
            })
          },
        },
        
        // WebSocket proxy for real-time features
        '/ws': {
          target: serverUrl,
          ws: true,
          changeOrigin: true,
        },
      },
      
      clearScreen: false,
    },
    
    build: {
      outDir: 'dist-web',
      sourcemap,
      minify: isBuild,
      
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom', 'react-router-dom'],
            ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
          },
        },
      },
    },
    
    // Preview server for production build testing
    preview: {
      port: 4173,
      proxy: {
        '/api/backend': {
          target: backendUrl,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/backend/, ''),
        },
        '/api': {
          target: serverUrl,
          changeOrigin: true,
        },
        '/payment': {
          target: serverUrl,
          changeOrigin: true,
        },
      },
    },
  }
})
