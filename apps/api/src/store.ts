import { MongoClient, Db } from 'mongodb';
import { setServers } from 'node:dns/promises';
import { mkdir, readFile, writeFile, rename } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { root } from './contracts.js';

type RecordData = { id: string; createdAt: string; updatedAt: string; [key: string]: any };
export class Store {
  db?: Db;
  client?: MongoClient;
  status = 'local';
  warning: string | null = null;
  private queue = Promise.resolve();
  constructor(public directory = path.join(root, 'runtime/data')) {}
  async init() {
    await mkdir(this.directory, { recursive: true });
    if (process.env.STORAGE_MODE === 'mongo' && process.env.MONGODB_URI) {
      try {
        const dnsServers = process.env.MONGODB_DNS_SERVERS?.trim();
        if (dnsServers && process.env.MONGODB_URI.startsWith('mongodb+srv://')) {
          // The driver uses Node's promise resolver for Atlas SRV and TXT records.
          setServers(dnsServers.split(',').map((server) => server.trim()));
        }
        this.client = new MongoClient(process.env.MONGODB_URI, {
          serverSelectionTimeoutMS: 5000,
          connectTimeoutMS: 5000,
        });
        await this.client.connect();
        this.db = this.client.db(process.env.MONGODB_DATABASE || 'infiniture');
        await this.db.command({ ping: 1 });
        this.status = 'mongodb';
      } catch (error) {
        await this.client?.close().catch(() => {});
        this.db = undefined;
        const failure = error as { syscall?: string; code?: string | number };
        let reason = 'MongoDB unavailable.';
        if (failure.syscall === 'querySrv' || failure.syscall === 'queryTxt') {
          reason = 'MongoDB DNS lookup failed. Check MONGODB_DNS_SERVERS.';
        } else if (failure.code === 'ERR_INVALID_IP_ADDRESS') {
          reason = 'MONGODB_DNS_SERVERS contains an invalid IP address.';
        } else if (failure.code === 18) {
          reason = 'MongoDB authentication failed.';
        }
        this.warning = `${reason} Using local JSON storage for this session.`;
      }
    }
  }
  async list(collection: string): Promise<RecordData[]> {
    if (this.db)
      return (await this.db
        .collection(collection)
        .find({}, { projection: { _id: 0 } })
        .sort({ updatedAt: -1 })
        .limit(200)
        .toArray()) as unknown as RecordData[];
    try {
      return JSON.parse(await readFile(path.join(this.directory, `${collection}.json`), 'utf8'));
    } catch (e: any) {
      if (e.code === 'ENOENT') return [];
      throw e;
    }
  }
  async get(collection: string, id: string) {
    return (await this.list(collection)).find((v) => v.id === id);
  }
  async put(collection: string, data: any, id: string = randomUUID()): Promise<RecordData> {
    const now = new Date().toISOString();
    const task = async () => {
      const old = await this.get(collection, id);
      const record = { ...data, id, createdAt: old?.createdAt || now, updatedAt: now };
      if (this.db)
        await this.db.collection(collection).replaceOne({ id }, record, { upsert: true });
      else {
        const items = await this.list(collection);
        const next = [record, ...items.filter((v) => v.id !== id)].slice(0, 200);
        const file = path.join(this.directory, `${collection}.json`);
        await writeFile(file + '.tmp', JSON.stringify(next));
        await rename(file + '.tmp', file);
      }
      return record;
    };
    const result = this.queue.then(task);
    this.queue = result.then(
      () => {},
      () => {},
    );
    return result;
  }
}
export const store = new Store();
