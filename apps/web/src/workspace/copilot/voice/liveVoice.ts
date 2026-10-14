// Gemini Live via Firebase AI Logic (spec §6.5). Firebase JS SDK 13 renamed VertexAIBackend to
// AgentPlatformBackend (same Vertex backend); the Live model is served in us-central1 only.
import { AgentPlatformBackend, getAI, getLiveGenerativeModel, ResponseModality, startAudioConversation } from 'firebase/ai'
import { app } from '@/firebase'
import type { StartLiveVoice } from '@/services/services'
import { LIVE_MODEL, LIVE_SYSTEM_INSTRUCTION, TOOL_DECLARATIONS } from './liveVoiceSpec'

export { LIVE_MODEL, LIVE_SYSTEM_INSTRUCTION, TOOL_DECLARATIONS }

export const startLiveVoice: StartLiveVoice = async ({ onToolCall }) => {
  const ai = getAI(app, { backend: new AgentPlatformBackend('us-central1') })
  const model = getLiveGenerativeModel(ai, {
    model: LIVE_MODEL,
    generationConfig: { responseModalities: [ResponseModality.AUDIO] },
    tools: [{ functionDeclarations: TOOL_DECLARATIONS }],
    systemInstruction: LIVE_SYSTEM_INSTRUCTION,
  })
  const session = await model.connect()
  const controller = await startAudioConversation(session, {
    functionCallingHandler: async (calls) => {
      const call = calls[0]
      const response = await onToolCall({ id: call.id, name: call.name, args: (call.args ?? {}) as Record<string, unknown> })
      return { id: call.id, name: call.name, response }
    },
  })
  return {
    stop: async () => {
      await controller.stop()
      await session.close()
    },
  }
}
