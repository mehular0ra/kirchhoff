import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { User } from 'firebase/auth'

// Mock Firebase modules
vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({})),
}))

vi.mock('firebase/auth', () => {
  let authStateCallback: ((user: User | null) => void) | null = null
  let unsubscribeSpy: ReturnType<typeof vi.fn> | null = null

  return {
    getAuth: vi.fn(() => ({ currentUser: null })),
    signInAnonymously: vi.fn(),
    onAuthStateChanged: vi.fn((_auth, callback) => {
      authStateCallback = callback
      unsubscribeSpy = vi.fn(() => {
        authStateCallback = null
      })
      return unsubscribeSpy
    }),
    __triggerAuthStateChange: (user: User | null) => {
      if (authStateCallback) authStateCallback(user)
    },
    __getUnsubscribeSpy: () => unsubscribeSpy,
  }
})

vi.mock('firebase/firestore', () => ({
  getFirestore: vi.fn(() => ({})),
}))

vi.mock('firebase/app-check', () => ({
  initializeAppCheck: vi.fn(),
  ReCaptchaEnterpriseProvider: vi.fn(),
  getToken: vi.fn(),
}))

import * as authModule from 'firebase/auth'

describe('ensureSignedIn', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset the cached promise by re-importing
    vi.resetModules()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('resolves immediately if currentUser exists', async () => {
    const mockUser = { uid: 'existing-uid' } as User
    vi.mocked(authModule.getAuth).mockReturnValue({ currentUser: mockUser } as any)

    // Need to re-import after mocking
    const { ensureSignedIn: ensureSignedIn2 } = await import('./firebase')
    const user = await ensureSignedIn2()
    expect(user).toBe(mockUser)
    expect(vi.mocked(authModule.signInAnonymously)).not.toHaveBeenCalled()
  })

  it('triggers signInAnonymously exactly once for concurrent calls', async () => {
    const mockUser = { uid: 'test-uid' } as User
    const mockSignInAnon = vi.fn().mockResolvedValue({ user: mockUser })
    vi.mocked(authModule.signInAnonymously).mockImplementation(mockSignInAnon)

    const mockGetAuth = vi.mocked(authModule.getAuth)
    mockGetAuth.mockReturnValue({ currentUser: null } as any)

    // Re-import to get fresh module state
    const { ensureSignedIn: ensureSignedIn2 } = await import('./firebase')

    // Start two concurrent calls
    const promise1 = ensureSignedIn2()
    const promise2 = ensureSignedIn2()

    // Simulate auth state change
    const mockOnAuthStateChanged = vi.mocked(authModule.onAuthStateChanged)
    const callback = mockOnAuthStateChanged.mock.calls[0]?.[1] as ((user: User | null) => void) | undefined
    if (callback) {
      callback(mockUser)
    }

    const [user1, user2] = await Promise.all([promise1, promise2])
    expect(user1).toBe(mockUser)
    expect(user2).toBe(mockUser)
    expect(mockSignInAnon).toHaveBeenCalledTimes(1)
  })

  it('unsubscribes listener on rejection and allows retry', async () => {
    const error = new Error('Sign in failed')
    const mockSignInAnon = vi.fn().mockRejectedValue(error)
    vi.mocked(authModule.signInAnonymously).mockImplementation(mockSignInAnon)

    const mockGetAuth = vi.mocked(authModule.getAuth)
    mockGetAuth.mockReturnValue({ currentUser: null } as any)

    const { ensureSignedIn: ensureSignedIn2 } = await import('./firebase')

    // First call should reject
    const promise1 = ensureSignedIn2()

    await expect(promise1).rejects.toThrow('Sign in failed')

    // Verify unsubscribe spy was called exactly once
    const unsubscribeSpy = (authModule as any).__getUnsubscribeSpy()
    expect(unsubscribeSpy).toHaveBeenCalledTimes(1)

    // Reset mocks for retry
    mockSignInAnon.mockClear()
    const mockOnAuthStateChanged = vi.mocked(authModule.onAuthStateChanged)
    mockOnAuthStateChanged.mockClear()

    // Second call should retry (not use cached failed promise)
    const mockUser = { uid: 'test-uid' } as User
    mockSignInAnon.mockResolvedValue({ user: mockUser })

    const promise2 = ensureSignedIn2()

    // Trigger auth state change
    const callback = mockOnAuthStateChanged.mock.calls[0]?.[1] as ((user: User | null) => void) | undefined
    if (callback) {
      callback(mockUser)
    }

    const user = await promise2
    expect(user).toBe(mockUser)
    expect(mockSignInAnon).toHaveBeenCalledTimes(1)
  })

  it('uses cached promise for concurrent calls before settlement', async () => {
    const mockUser = { uid: 'test-uid' } as User
    const mockSignInAnon = vi.fn().mockResolvedValue({ user: mockUser })
    vi.mocked(authModule.signInAnonymously).mockImplementation(mockSignInAnon)

    const mockGetAuth = vi.mocked(authModule.getAuth)
    mockGetAuth.mockReturnValue({ currentUser: null } as any)

    const { ensureSignedIn: ensureSignedIn2 } = await import('./firebase')

    // Make three concurrent calls
    const promise1 = ensureSignedIn2()
    const promise2 = ensureSignedIn2()
    const promise3 = ensureSignedIn2()

    expect(promise1).toBe(promise2)
    expect(promise2).toBe(promise3)

    // Simulate auth state change
    const mockOnAuthStateChanged = vi.mocked(authModule.onAuthStateChanged)
    const callback = mockOnAuthStateChanged.mock.calls[0]?.[1] as ((user: User | null) => void) | undefined
    if (callback) {
      callback(mockUser)
    }

    const [user1, user2, user3] = await Promise.all([promise1, promise2, promise3])
    expect(user1).toBe(mockUser)
    expect(user2).toBe(mockUser)
    expect(user3).toBe(mockUser)
    expect(mockSignInAnon).toHaveBeenCalledTimes(1)
  })
})
