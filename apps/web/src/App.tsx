import { collection, onSnapshot, orderBy, query } from 'firebase/firestore'
import { useCallback } from 'react'
import { apiFetch } from './api'
import { auth, db } from './firebase'
import { HelloRun } from './hello/HelloRun'
import type { RunEvent } from './contracts/generated'

export default function App() {
  const start = useCallback(async () => {
    const r = await apiFetch('/api/hello-run', { method: 'POST' })
    if (!r.ok) throw new Error(`hello-run failed: ${r.status}`)
    return (await r.json()).run_id as string
  }, [])
  const subscribe = useCallback((runId: string, cb: (e: RunEvent[]) => void) => {
    const uid = auth.currentUser!.uid
    const q = query(collection(db, `workspaces/${uid}/runs/${runId}/events`), orderBy('seq'))
    return onSnapshot(q, (snap) => cb(snap.docs.map((d) => d.data() as RunEvent)))
  }, [])
  return <HelloRun start={start} subscribe={subscribe} />
}
