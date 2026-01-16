import Surreal from 'surrealdb';
import { env } from '$env/dynamic/private';

const SURREALDB_URL = env.SURREALDB_URL || 'ws://localhost:8001';
const SURREALDB_USER = env.SURREALDB_USER || 'root';
const SURREALDB_PASS = env.SURREALDB_PASS || 'root';
const SURREALDB_NS = env.SURREALDB_NS || 'glider';
const SURREALDB_DB = env.SURREALDB_DB || 'glider';

export async function getDb(): Promise<Surreal> {
	const db = new Surreal();
	await db.connect(SURREALDB_URL);
	await db.signin({
		username: SURREALDB_USER,
		password: SURREALDB_PASS
	});
	await db.use({
		namespace: SURREALDB_NS,
		database: SURREALDB_DB
	});
	return db;
}

export async function withDb<T>(fn: (db: Surreal) => Promise<T>): Promise<T> {
	const db = await getDb();
	try {
		return await fn(db);
	} finally {
		await db.close();
	}
}
