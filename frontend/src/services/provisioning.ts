import api from '../lib/axios'
import { useAuthStore } from '../stores/authStore'

// SSE 流事件类型
export interface ProvisioningStreamEvent {
  type: 'progress' | 'user_created' | 'user_failed' | 'summary' | 'error'
  // progress
  total?: number
  done?: number
  // user_created / user_failed
  username?: string
  email?: string
  plan?: string
  error?: string
  // summary
  task_id?: string
  success_count?: number
  fail_count?: number
}

export interface PlanItem {
  subscription_type: string
  count: number
}

export interface ProvisioningPayload {
  prefix: string
  domain: string
  plans: PlanItem[]
}

/**
 * 发起批量开通 SSE 流式请求
 * 使用 fetch 而非原生 EventSource，以支持 POST + Authorization header
 */
export async function streamProvisioning(
  accountId: number,
  payload: ProvisioningPayload,
  onEvent: (event: ProvisioningStreamEvent) => void,
  onDone: () => void,
  onError: (err: Error) => void,
): Promise<AbortController> {
  const ctrl = new AbortController()
  const token = useAuthStore.getState().accessToken

  const doFetch = async () => {
    const res = await fetch(`/api/v1/accounts/${accountId}/provisioning`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    })

    if (!res.ok) {
      onError(new Error(`HTTP ${res.status}: ${res.statusText}`))
      return
    }

    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        onDone()
        break
      }
      buf += decoder.decode(value, { stream: true })
      // SSE 按行解析
      const lines = buf.split('\n')
      buf = lines.pop() ?? ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const raw = line.slice(6).trim()
          if (raw === '[DONE]') {
            onDone()
            return
          }
          try {
            const parsed = JSON.parse(raw) as ProvisioningStreamEvent
            onEvent(parsed)
          } catch {
            // 忽略非 JSON 行
          }
        }
      }
    }
  }

  doFetch().catch((e: Error) => {
    if (e.name !== 'AbortError') {
      onError(e)
    }
  })

  return ctrl
}

export const provisioningApi = {
  tasks: (accountId: number) =>
    api.get<{ items: { id: string; status: string; created_at: string }[] }>(
      `/accounts/${accountId}/provisioning/tasks`,
    ),

  exportJson: (accountId: number, taskId: string) =>
    api.post(
      `/accounts/${accountId}/provisioning/export/${taskId}`,
      {},
      { responseType: 'blob' },
    ),
}
