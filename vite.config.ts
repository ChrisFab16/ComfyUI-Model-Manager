// vite.config.ts
import vue from '@vitejs/plugin-vue'
import fs from 'node:fs'
import path from 'node:path'
import { defineConfig, Plugin } from 'vite'

function dev(): Plugin {
  return {
    name: 'vite-plugin-dev-fix',
    apply: 'serve',
    enforce: 'post',
    configureServer(server) {
      server.httpServer?.on('listening', () => {
        const rootDir = server.config.root
        const outDir = server.config.build.outDir
        const outDirPath = path.join(rootDir, outDir)
        if (fs.existsSync(outDirPath)) {
          fs.rmSync(outDirPath, { recursive: true })
        }
        fs.mkdirSync(outDirPath)
        const port = server.config.server.port
        const content = `import "http://localhost:${port}/src/main.ts";`
        fs.writeFileSync(path.join(outDirPath, 'manager-dev.js'), content)
      })
    },
  }
}

function createWebVersion(): Plugin {
  return {
    name: 'vite-plugin-web-version',
    apply: 'build',
    enforce: 'post',
    writeBundle() {
      const pyProjectContent = fs.readFileSync('pyproject.toml', 'utf8')
      const [, version] = pyProjectContent.match(/version = "(.*)"/) ?? []
      const metadata = [
        `version: ${version}`,
        `build_time: ${new Date().toISOString()}`,
        '',
      ].join('\n')
      const metadataFilePath = path.join(__dirname, 'web', 'version.yaml')
      fs.writeFileSync(metadataFilePath, metadata, 'utf-8')
    },
  }
}

function cleanWebDir(): Plugin {
  return {
    name: 'vite-plugin-clean-web-dir',
    apply: 'build',
    enforce: 'pre',
    buildStart() {
      const webDir = path.join(__dirname, 'web')
      if (fs.existsSync(webDir)) {
        fs.rmSync(webDir, { recursive: true })
      }
    },
  }
}

export default defineConfig({
  plugins: [vue(), dev(), createWebVersion(), cleanWebDir()],
  base: '/extensions/ComfyUI-Model-Manager/',
  build: {
    outDir: 'web',
    minify: false,
    target: 'es2022',
    sourcemap: false,
    rollupOptions: {
      treeshake: false,
      output: {
        manualChunks(id) {
          if (id.includes('primevue')) {
            return 'primevue'
          }
        },
        minifyInternalExports: false,
      },
    },
    chunkSizeWarningLimit: 1024,
  },
  resolve: {
    alias: {
      src: path.resolve(__dirname, 'src'),
      components: path.resolve(__dirname, 'src/components'),
      hooks: path.resolve(__dirname, 'src/hooks'),
      scripts: path.resolve(__dirname, 'src/scripts'),
      types: path.resolve(__dirname, 'src/types'),
      utils: path.resolve(__dirname, 'src/utils'),
    },
  },
  server: {
    proxy: {
      '/model-manager': {
        target: 'http://127.0.0.1:8188',
        changeOrigin: true,
        rewrite: (path) => path, // Pass path unchanged
      },
      '/api': {
        target: 'http://127.0.0.1:8188',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/api'),
      },
    },
  },
})
