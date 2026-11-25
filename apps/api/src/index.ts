import dotenv from 'dotenv';
dotenv.config({ path: new URL('../.env', import.meta.url) });
// Dynamic import ensures environment variables exist before provider initialization.
await import('./server.js');
