import { afterEach, describe, expect, it } from 'vitest'

import {
  setWorkspaceCredential,
  workspaceAuthorizationHeaders,
} from './workspaceAuth'

afterEach(() => setWorkspaceCredential(null))

describe('workspace authentication', () => {
  it('keeps the credential in memory and emits only an authorization header', () => {
    setWorkspaceCredential(' private-local-credential ')

    expect(workspaceAuthorizationHeaders()).toEqual({
      Authorization: 'Bearer private-local-credential',
    })

    setWorkspaceCredential(null)
    expect(workspaceAuthorizationHeaders()).toEqual({})
  })
})
