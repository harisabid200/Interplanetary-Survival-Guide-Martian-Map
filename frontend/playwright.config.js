import {defineConfig} from '@playwright/test';
const apiPort=Number(process.env.MARSWALK_API_PORT||8000);
if (!Number.isInteger(apiPort)||apiPort<1024||apiPort>65535) throw new Error('Invalid test API port');
export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {baseURL: 'http://127.0.0.1:4173', channel: 'chrome', headless: true},
  webServer: [
    {command: `".venv/Scripts/python.exe" -m uvicorn backend.api:app --host 127.0.0.1 --port ${apiPort} --limit-concurrency 16`, cwd: '..', url: `http://127.0.0.1:${apiPort}/api/health`, reuseExistingServer: false, timeout: 30000},
    {command: 'npm run preview', url: 'http://127.0.0.1:4173', reuseExistingServer: false, timeout: 30000},
  ],
});
