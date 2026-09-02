import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'risk-snapshot',
              test: /src[\\/]data[\\/]precautionSnapshot\.json$/,
              priority: 2,
            },
            {
              name: 'react-vendor',
              test: /node_modules[\\/](react|react-dom)[\\/]/,
              priority: 1,
            },
          ],
        },
      },
    },
  },
})
