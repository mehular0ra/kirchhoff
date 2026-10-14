import type { InboxSnapshot, IntegrationsSnapshot, ProjectBundle, World } from '@/lib/types'
import { normalizeBundle, type Bundle } from '@/lib/types'
import hallMini from './hall-mini.json'
import inbox from './inbox.json'
import integrations from './integrations.json'
import world from './world.json'

/** Fresh deep copy each call so tests can mutate freely. */
export function fixtureBundle(): Bundle {
  return normalizeBundle(structuredClone(hallMini) as unknown as ProjectBundle)
}

export function fixtureWorld(): World {
  return structuredClone(world) as unknown as World
}

export function fixtureIntegrations(): IntegrationsSnapshot {
  return structuredClone(integrations) as unknown as IntegrationsSnapshot
}

export function fixtureInbox(): InboxSnapshot {
  return structuredClone(inbox) as unknown as InboxSnapshot
}
