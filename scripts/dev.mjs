import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const processes = [];
for (const [command, args] of [
  [
    'python',
    [
      '-m',
      'uvicorn',
      'services.engine.app:app',
      '--host',
      '127.0.0.1',
      '--port',
      '8000',
      '--reload',
      '--reload-dir',
      'services/engine',
    ],
  ],
  ['node', ['node_modules/tsx/dist/cli.mjs', 'watch', 'apps/api/src/index.ts']],
  [
    'node',
    [
      'node_modules/vite/bin/vite.js',
      '--config',
      'apps/web/vite.config.ts',
      '--host',
      '127.0.0.1',
      'apps/web',
    ],
  ],
]) {
  const child = spawn(command, args, { cwd: root, stdio: 'inherit', windowsHide: true });
  processes.push(child);
  child.on('error', (e) => console.error(e.message));
}
console.log('Infiniture studio: http://127.0.0.1:5174');
for (const signal of ['SIGINT', 'SIGTERM'])
  process.on(signal, () => {
    for (const p of processes) p.kill();
    process.exit();
  });
