import type { Application, AnalyzeEvent, ProfileDetail, ProfileSummary } from '@/types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  profiles: {
    list: (): Promise<ProfileSummary[]> => request('/profiles'),
    get: (id: number): Promise<ProfileDetail> => request(`/profiles/${id}`),
    create: (body: FormData): Promise<{ id: number }> =>
      request('/profiles', { method: 'POST', body }),
    update: (id: number, body: FormData): Promise<{ id: number }> =>
      request(`/profiles/${id}`, { method: 'PUT', body }),
    delete: async (id: number): Promise<void> => {
      const res = await fetch(`/api/profiles/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
    },
  },

  applications: {
    list: (profileId: number | null): Promise<Application[]> =>
      request(profileId != null ? `/applications?profile_id=${profileId}` : '/applications'),
    cvDocxUrl: (id: number): string => `${BASE}/applications/${id}/cv.docx`,
    anschreibenDocxUrl: (id: number): string => `${BASE}/applications/${id}/anschreiben.docx`,
    patchAnschreiben: async (id: number, anschreiben: string): Promise<void> => {
      const res = await fetch(`${BASE}/applications/${id}/anschreiben`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anschreiben }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
    },
  },
}

export async function* streamAnalyze(
  profileId: number,
  jobPosting: string,
): AsyncGenerator<AnalyzeEvent> {
  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: profileId, job_posting: jobPosting }),
  })

  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `HTTP ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6)) as AnalyzeEvent
          yield event
        } catch {
          // skip malformed
        }
      }
    }
  }
}
