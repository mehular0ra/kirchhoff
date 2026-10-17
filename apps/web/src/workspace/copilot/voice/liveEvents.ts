// What the co-pilot panel needs to know about a Gemini Live conversation, beyond its tool calls: what the visitor
// said, whether the model is replying, and when a turn ends. The SDK's startAudioConversation reads the session's
// message stream itself and hands the app only the tool calls, so the stream is tee'd here (teeReceive) without
// touching the audio path.
import type { LiveVoiceEvent } from '@/services/services'

export type { LiveVoiceEvent }

/** The part of a Live server message used here: a structural subset of the SDK's LiveServerContent. */
export interface LiveMessage {
  type: string
  inputTranscription?: { text?: string }
  outputTranscription?: { text?: string }
  modelTurn?: { parts?: Array<{ type?: string; inlineData?: { mimeType?: string } } | undefined> }
  turnComplete?: boolean
  interrupted?: boolean
}

/**
 * Turns Live messages into panel events. The model's own transcript is only used to know that it is speaking: its
 * words are never passed on, because the written answer on screen is the engine's (spec §6.3).
 */
export function makeLiveObserver(emit: (e: LiveVoiceEvent) => void): (m: LiveMessage) => void {
  let speaking = false
  return (m) => {
    if (m.type !== 'serverContent') return
    const heard = m.inputTranscription?.text
    if (heard) emit({ type: 'heard', text: heard })
    const audio = m.modelTurn?.parts?.some((p) => p?.type === 'inlineData' && p.inlineData?.mimeType?.startsWith('audio/'))
    if ((audio || m.outputTranscription?.text) && !speaking) {
      speaking = true
      emit({ type: 'speaking' })
    }
    if (m.turnComplete || m.interrupted) {
      speaking = false
      emit({ type: 'turn_complete' })
    }
  }
}

/**
 * Replaces `session.receive` with a stream that shows every message to `onMessage` and passes it on unchanged, so
 * startAudioConversation (which calls receive() once and plays the audio) still gets exactly what it expects. A
 * watcher that throws is ignored: the conversation never depends on the panel.
 */
export function teeReceive<M>(session: { receive(): AsyncGenerator<M, void, unknown> }, onMessage: (m: M) => void): void {
  const original = session.receive.bind(session)
  session.receive = () =>
    (async function* () {
      for await (const m of original()) {
        try {
          onMessage(m)
        } catch {
          // the panel's bug must not stop the audio
        }
        yield m
      }
    })()
}
