// Minimal read-only Firestore surface used by the live adapter. Clients only read their own
// workspace (`workspaces/{uid}/**`); they never write (spec §14).
import {
  collection,
  doc,
  getDoc,
  onSnapshot,
  orderBy,
  query,
  where,
  type Firestore,
  type QueryConstraint,
} from 'firebase/firestore'

export interface DocSnap {
  id: string
  data: Record<string, unknown>
}
export type Unsubscribe = () => void
export interface CollectionQuery {
  where?: [field: string, op: '==', value: string]
  orderBy?: string
}

export interface LiveSource {
  watchDoc(path: string, cb: (d: DocSnap | null) => void, onError?: (e: Error) => void): Unsubscribe
  watchCollection(
    path: string,
    cb: (docs: DocSnap[]) => void,
    q?: CollectionQuery,
    onError?: (e: Error) => void,
  ): Unsubscribe
  getDoc(path: string): Promise<DocSnap | null>
}

export function firestoreSource(db: Firestore): LiveSource {
  return {
    watchDoc(path, cb, onError) {
      return onSnapshot(
        doc(db, path),
        (s) => cb(s.exists() ? { id: s.id, data: s.data() } : null),
        (e) => onError?.(e),
      )
    },
    watchCollection(path, cb, q, onError) {
      const constraints: QueryConstraint[] = []
      if (q?.where) constraints.push(where(q.where[0], q.where[1], q.where[2]))
      if (q?.orderBy) constraints.push(orderBy(q.orderBy))
      return onSnapshot(
        query(collection(db, path), ...constraints),
        (s) => cb(s.docs.map((d) => ({ id: d.id, data: d.data() }))),
        (e) => onError?.(e),
      )
    },
    async getDoc(path) {
      const s = await getDoc(doc(db, path))
      return s.exists() ? { id: s.id, data: s.data() } : null
    },
  }
}
