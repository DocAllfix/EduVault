/**
 * F-STUDIO-UX Step 4 (2026-06-02): cache PPTX binary in IndexedDB.
 *
 * Strategia:
 *  - Chiave: `${courseId}_${rebuildToken}` (token = unix timestamp di
 *    courses.last_rebuilt_at, gia` usato dal backend per cache PNG preview).
 *    Quando il backend rigenera il corso, il token cambia → cache automaticamente
 *    stale per quel corso.
 *  - LRU eviction: massimo 3 corsi cachati simultaneamente. Browser quota
 *    IndexedDB e` ~50-100MB tipica; 3 × 25MB PPTX = ~75MB margine.
 *  - API: getCached(key) / setCached(key, blob) / clearStale(currentTokens)
 *
 * idb-keyval e` una libreria minimale (2KB gzipped) basata su Promise API.
 * Nessuna gestione complicata di store/transactions: chiave/valore semplice.
 */

import { createStore, get, set, del, keys } from 'idb-keyval'

const STORE_NAME = 'eduvault-pptx-cache'
const DB_NAME = 'eduvault-studio'

const _store = createStore(DB_NAME, STORE_NAME)

const MAX_ENTRIES = 3

export interface CachedPptx {
  /** Binary del PPTX. Blob preferito perche` IndexedDB lo serializza nativo. */
  blob: Blob
  /** Timestamp di quando questa entry e` stata cachata (Date.now()). */
  cachedAt: number
  /** Bytes dell'entry per metriche / debugging. */
  size: number
}

/**
 * Costruisce la chiave cache.
 *
 * `rebuildToken` deve essere stable per la stessa versione del PPTX. Usiamo il
 * Unix timestamp di `courses.last_rebuilt_at` (cosi` quando il backend ricostruisce
 * il PPTX, il token cambia → cache invalida automaticamente).
 */
export function buildCacheKey(courseId: string, rebuildToken: string): string {
  return `${courseId}__${rebuildToken}`
}

/**
 * Ritorna l'entry cachata, o `undefined` se mancante.
 *
 * NON aggiorna `cachedAt` (per non corrompere l'ordine LRU). Per "touch"
 * espliciti usa la `touchCached`.
 */
export async function getCached(
  key: string,
): Promise<CachedPptx | undefined> {
  try {
    return (await get<CachedPptx>(key, _store)) ?? undefined
  } catch {
    return undefined
  }
}

/**
 * Salva un PPTX in cache. Esegue eviction LRU prima della scrittura se
 * superato `MAX_ENTRIES`.
 */
export async function setCached(key: string, blob: Blob): Promise<void> {
  try {
    await evictLRUIfNeeded()
    const entry: CachedPptx = {
      blob,
      cachedAt: Date.now(),
      size: blob.size,
    }
    await set(key, entry, _store)
  } catch {
    // IndexedDB pieno o blocked: silently fail (caller continuera` con fresh fetch).
  }
}

/**
 * Rimuove le entry che NON appartengono ai `validKeys` correnti. Utile per
 * pulizia: quando l'utente apre un corso, sappiamo che le chiavi dei corsi
 * con `rebuild_token` diverso (versioni vecchie) sono stale → si possono
 * rimuovere.
 *
 * Mantiene comunque le entry di altri corsi (non in `validKeys`) per LRU.
 */
export async function pruneStaleVersions(
  courseId: string,
  validRebuildToken: string,
): Promise<void> {
  try {
    const allKeys = await keys(_store)
    const prefix = `${courseId}__`
    const validKey = buildCacheKey(courseId, validRebuildToken)
    for (const k of allKeys) {
      const keyStr = String(k)
      if (keyStr.startsWith(prefix) && keyStr !== validKey) {
        await del(k, _store)
      }
    }
  } catch {
    // ignore
  }
}

async function evictLRUIfNeeded(): Promise<void> {
  const allKeys = await keys(_store)
  if (allKeys.length < MAX_ENTRIES) return
  // Load all entries con cachedAt per ordinare LRU.
  const withTimestamps: Array<{ key: IDBValidKey; cachedAt: number }> = []
  for (const k of allKeys) {
    const entry = await get<CachedPptx>(k, _store)
    if (entry) withTimestamps.push({ key: k, cachedAt: entry.cachedAt })
  }
  withTimestamps.sort((a, b) => a.cachedAt - b.cachedAt) // oldest first
  // Rimuovi le piu` vecchie finche` non scendiamo sotto MAX_ENTRIES - 1
  // (lasciamo spazio per la nuova entry).
  const toRemove = withTimestamps.slice(0, withTimestamps.length - MAX_ENTRIES + 1)
  for (const { key } of toRemove) {
    await del(key, _store)
  }
}
