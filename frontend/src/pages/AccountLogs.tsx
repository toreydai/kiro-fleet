import { useEffect, useState, useCallback } from 'react'
import { Table, Select, Typography, Tag } from 'antd'
import { accountsApi } from '../services/accounts'
import type { Account } from '../stores/appStore'
import api from '../lib/axios'
import { fmtDate } from '../lib/utils'

const { Title } = Typography

interface LogEntry {
  id: string | number
  action: string
  target?: string
  operator?: string
  status?: string
  detail?: string
  created_at: string
}

export default function AccountLogs() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | undefined>(undefined)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    accountsApi.list().then((res) => {
      const raw = res.data
      const list: Account[] = Array.isArray(raw) ? raw : (raw as { items: Account[] }).items ?? []
      setAccounts(list)
      if (list.length > 0) setSelectedAccountId(list[0].id)
    })
  }, [])

  const loadLogs = useCallback(() => {
    if (!selectedAccountId) return
    setLoading(true)
    api
      .get<{ items: LogEntry[] } | LogEntry[]>(`/accounts/${selectedAccountId}/logs`)
      .then((res) => {
        const raw = res.data
        setLogs(Array.isArray(raw) ? raw : (raw as { items: LogEntry[] }).items ?? [])
      })
      .finally(() => setLoading(false))
  }, [selectedAccountId])

  useEffect(() => {
    loadLogs()
  }, [loadLogs])

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: fmtDate,
      width: 160,
      sorter: (a: LogEntry, b: LogEntry) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      defaultSortOrder: 'descend' as const,
    },
    { title: '操作', dataIndex: 'action', key: 'action', width: 160 },
    { title: '目标', dataIndex: 'target', key: 'target' },
    { title: '操作人', dataIndex: 'operator', key: 'operator', width: 120 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s?: string) => {
        if (!s) return '-'
        const colorMap: Record<string, string> = {
          success: 'green',
          failed: 'red',
          error: 'red',
          pending: 'orange',
        }
        return <Tag color={colorMap[s] ?? 'blue'}>{s}</Tag>
      },
    },
    {
      title: '详情',
      dataIndex: 'detail',
      key: 'detail',
      ellipsis: true,
    },
  ]

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          操作日志
        </Title>
        <Select
          placeholder="选择账号"
          value={selectedAccountId}
          onChange={setSelectedAccountId}
          style={{ width: 220 }}
          options={accounts.map((a) => ({ value: a.id, label: a.name }))}
        />
      </div>
      <Table
        dataSource={logs}
        columns={columns}
        rowKey="id"
        loading={loading}
        scroll={{ x: 900 }}
        size="small"
      />
    </div>
  )
}
