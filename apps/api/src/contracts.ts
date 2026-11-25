import Ajv from 'ajv';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const ajv = new Ajv.default({ allErrors: true, strict: false });
export const schemas = Object.fromEntries(
  ['generate', 'scene', 'asset', 'validate', 'plan'].map((n) => [
    n,
    JSON.parse(readFileSync(path.join(root, `packages/shared/${n}.schema.json`), 'utf8')),
  ]),
);
const validators = Object.fromEntries(Object.entries(schemas).map(([n, s]) => [n, ajv.compile(s)]));
export function check(name: string, data: unknown) {
  const validator = validators[name];
  if (!validator(data)) {
    const error = new Error(`Invalid ${name} data`);
    Object.assign(error, { status: 422, details: validator.errors });
    throw error;
  }
  return data;
}
export const baseAssets: any[] = JSON.parse(
  readFileSync(path.join(root, 'packages/shared/assets.json'), 'utf8'),
);
