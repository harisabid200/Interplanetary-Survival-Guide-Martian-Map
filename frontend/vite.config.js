import {defineConfig} from 'vite';
import {fileURLToPath} from 'node:url';
const apiPort=Number(process.env.MARSWALK_API_PORT||8000);
if (!Number.isInteger(apiPort)||apiPort<1024||apiPort>65535) throw new Error('MARSWALK_API_PORT must be a local TCP port');
const apiProxy = {'/api': {target: `http://127.0.0.1:${apiPort}`, changeOrigin: true}};
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  server: {port: 5173, strictPort: true, proxy: apiProxy},
  preview: {proxy: apiProxy},
});
