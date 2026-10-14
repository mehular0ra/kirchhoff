// Push-to-talk fallback (spec §6.5): record a clip, POST /api/voice, speak the answer with the
// browser's speech synthesis. Spoken audio (both Live and this synthesized reply) is not run
// through the digit filter: only the engine-built text the panel shows on screen is (spec §6.3).

export interface Recording {
  stop(): Promise<Blob>
}

export function canRecord(): boolean {
  return typeof window !== 'undefined' && 'MediaRecorder' in window && !!navigator.mediaDevices?.getUserMedia
}

export async function startRecording(): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg'
  const rec = new MediaRecorder(stream, { mimeType: mime })
  const chunks: Blob[] = []
  rec.ondataavailable = (e) => chunks.push(e.data)
  rec.start()
  return {
    stop: () =>
      new Promise<Blob>((resolve) => {
        rec.onstop = () => {
          stream.getTracks().forEach((t) => t.stop())
          resolve(new Blob(chunks, { type: mime }))
        }
        rec.stop()
      }),
  }
}

export function speak(text: string): void {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(text))
}
