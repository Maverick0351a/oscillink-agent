let workspaceCredential: string | null = null

export function setWorkspaceCredential(credential: string | null) {
  const normalized = credential?.trim() ?? ''
  workspaceCredential = normalized.length > 0 ? normalized : null
}

export function workspaceAuthorizationHeaders(): Record<string, string> {
  return workspaceCredential === null
    ? {}
    : { Authorization: `Bearer ${workspaceCredential}` }
}
