import dayjs from 'dayjs'

// 订阅类型 → 中文显示名
export const SUB_LABEL: Record<string, string> = {
  Q_DEVELOPER_STANDALONE_PRO: 'Pro',
  Q_DEVELOPER_STANDALONE_POWER: 'Power',
  Q_DEVELOPER_STANDALONE_PRO_PLUS: 'Pro Plus',
  KIRO_ENTERPRISE_PRO: 'Kiro Pro',
  KIRO_ENTERPRISE_PRO_PLUS: 'Kiro Pro+',
  KIRO_ENTERPRISE_PRO_MAX: 'Kiro Pro Max',
  KIRO_ENTERPRISE_PRO_POWER: 'Kiro Power',
}

export function subLabel(type: string): string {
  return SUB_LABEL[type] ?? type
}

// 日期格式化
export function fmtDate(date?: string | null): string {
  if (!date) return '-'
  return dayjs(date).format('YYYY-MM-DD HH:mm')
}

export function fmtDateShort(date?: string | null): string {
  if (!date) return '-'
  return dayjs(date).format('YYYY-MM-DD')
}

// 账号状态样式
export const ACCOUNT_STATUS_COLOR: Record<string, string> = {
  active: 'green',
  pending: 'orange',
  invalid: 'red',
}

export const ACCOUNT_STATUS_LABEL: Record<string, string> = {
  active: '正常',
  pending: '待验证',
  invalid: '无效',
}

// 从 axios 错误中提取可读信息
export function extractErrMsg(e: unknown, fallback = '操作失败'): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string }
  return err.response?.data?.detail ?? err.message ?? fallback
}
