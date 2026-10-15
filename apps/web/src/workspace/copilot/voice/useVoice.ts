// Voice state machine: Gemini Live first; on failure (or when Live is not configured) switch
// automatically to push-to-talk via POST /api/voice (spec §6.5).
import { useEffect, useRef, useState } from 'react'
import { ApiError, describeApiError, type VoiceResponse } from '@/services/apiClient'
import { useServices, type LiveVoiceCall, type LiveVoiceHandle } from '@/services/services'
import { canRecord, startRecording, type Recording } from './pushToTalk'

export type VoiceMode = 'off' | 'connecting' | 'live' | 'ptt' | 'recording' | 'thinking'

const LIVE_TIMEOUT_MS = 8000

export function useVoice(opts: {
  /** What push-to-talk sends as revision_ref: the what-if revision (head unless picked in the revision bar, #37). */
  revisionRef: string | null
  onToolCall: (call: LiveVoiceCall) => Promise<Record<string, unknown>>
  /** `revisionRef` is the one this answer was asked on, so the answer can name that revision. */
  onPushToTalk: (res: VoiceResponse, revisionRef: string) => void
}) {
  const { api, startLiveVoice } = useServices()
  const [mode, setMode] = useState<VoiceMode>('off')
  const [note, setNote] = useState<string | null>(null)
  const live = useRef<LiveVoiceHandle | null>(null)
  const rec = useRef<Recording | null>(null)
  const optsRef = useRef(opts)
  useEffect(() => {
    optsRef.current = opts
  }, [opts])

  useEffect(
    () => () => {
      // Never leave a mic stream or a spoken reply running past unmount (ruling P3-R2 fix round 1).
      void live.current?.stop().catch(() => undefined)
      // Discards the in-progress clip: Recording.stop() stops the MediaRecorder and, via its own
      // onstop handler, every track of the underlying getUserMedia stream (pushToTalk.ts). The
      // resulting blob is never sent — only pttUp() does that, and it is not called here.
      void rec.current?.stop().catch(() => undefined)
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel()
    },
    [],
  )

  const startLive = async () => {
    setNote(null)
    if (!startLiveVoice) {
      setMode('ptt')
      setNote('Live voice is not available here; hold the button to talk.')
      return
    }
    setMode('connecting')
    try {
      live.current = await Promise.race([
        startLiveVoice({ onToolCall: (c) => optsRef.current.onToolCall(c) }),
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error('timeout')), LIVE_TIMEOUT_MS)),
      ])
      setMode('live')
    } catch {
      setMode('ptt')
      setNote('Gemini Live could not connect; switched to push-to-talk.')
    }
  }

  const stopLive = async () => {
    await live.current?.stop().catch(() => undefined)
    live.current = null
    setMode('off')
  }

  const pttDown = async () => {
    if (!canRecord()) {
      setNote('This browser cannot record audio; use the typed box.')
      return
    }
    try {
      rec.current = await startRecording()
      setMode('recording')
    } catch {
      setNote('Microphone permission was denied; use the typed box.')
    }
  }

  const pttUp = async () => {
    const r = rec.current
    if (!r) return
    rec.current = null
    setMode('thinking')
    try {
      const blob = await r.stop()
      const ref = optsRef.current.revisionRef
      if (!ref) throw new Error('no revision')
      optsRef.current.onPushToTalk(await api.voice(blob, ref), ref)
    } catch (e) {
      // A transient model error (503 voice_unavailable, issue #36) is worth retrying; say so.
      setNote(
        e instanceof ApiError && e.detail === 'voice_unavailable'
          ? describeApiError(e)
          : 'The voice service is unreachable; use the typed box or the chips.',
      )
    } finally {
      setMode('ptt')
    }
  }

  return { mode, note, startLive, stopLive, pttDown, pttUp }
}
