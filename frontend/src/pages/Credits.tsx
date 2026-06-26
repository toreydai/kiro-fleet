import { useEffect, useState, useCallback } from 'react'
import {
  Table,
  Button,
  Select,
  Space,
  Typography,
  Card,
  Statistic,
  Row,
  Col,
  message,
  Progress,
} from 'antd'
import { SyncOutlined } from '@ant-design/icons'
import { creditsApi, type CreditRecord, type CreditSummary } from '../services/credits'
import { accountsApi } from '../services/accounts'
import type { Account } from '../stores/appStore'
import { fmtDate, extractErrMsg } from '../lib/utils'

const { Title } = Typography

export default function Credits() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | undefined>(undefined)
  const [credits, setCredits] = useState<CreditRecord[]>([])
  const [summary, setSummary] = useState<CreditSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    accountsApi.list().then((res) => {
      const raw = res.data
      const list: Account[] = Array.isArray(raw) ? raw : (raw as { items: Account[] }).items ?? []
      setAccounts(list)
      if (list.length > 0) setSelectedAccountId(list[0].id)
    })
  }, [])

  const load = useCallback(() => {
    if (!selectedAccountId) return
    setLoading(true)
    creditsApi
      .list(selectedAccountId)
      .then((res) => {
        const raw = res.data
        if (Array.isArray(raw)) {
          setCredits(raw)
          setSummary(null)
        } else {
          const typed = raw as { items: CreditRecord[]; summary?: CreditSummary }
          setCredits(typed.items ?? [])
          if (typed.summary) setSummary(typed.summary)
        }
      })
      .finally(() => setLoading(false))
  }, [selectedAccountId])

  useEffect(() => {
    load()
  }, [load])

  const onSync = async () => {
    if (!selectedAccountId) return
    setSyncing(true)
    try {
      await creditsApi.sync(selectedAccountId)
      void message.success('同步成功，数据已刷新')
      load()
    } catch (e) {
      void message.error(extractErrMsg(e, '同步失败'))
    } finally {
      setSyncing(false)
    }
  }

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '已用',
      dataIndex: 'used',
      key: 'used',
      render: (v: number) => v?.toLocaleString() ?? '-',
      sorter: (a: CreditRecord, b: CreditRecord) => (a.used ?? 0) - (b.used ?? 0),
    },
    {
      title: '剩余',
      dataIndex: 'remaining',
      key: 'remaining',
      render: (v: number) => v?.toLocaleString() ?? '-',
    },
    {
      title: '总量',
      dataIndex: 'total',
      key: 'total',
      render: (v: number) => v?.toLocaleString() ?? '-',
    },
    {
      title: '使用率',
      key: 'usage_rate',
      render: (_: unknown, record: CreditRecord) => {
        if (!record.total) return '-'
        const pct = Math.round(((record.used ?? 0) / record.total) * 100)
        return (
          <Progress
            percent={pct}
            size="small"
            strokeColor={pct > 80 ? '#ff4d4f' : pct > 60 ? '#faad14' : '#52c41a'}
            style={{ minWidth: 80 }}
          />
        )
      },
    },
    { title: '周期', dataIndex: 'period', key: 'period' },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: fmtDate,
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
          Credit 用量统计
        </Title>
        <Space>
          <Select
            placeholder="选择账号"
            value={selectedAccountId}
            onChange={setSelectedAccountId}
            style={{ width: 220 }}
            options={accounts.map((a) => ({ value: a.id, label: a.name }))}
          />
          <Button
            icon={<SyncOutlined />}
            loading={syncing}
            onClick={onSync}
            disabled={!selectedAccountId}
          >
            同步
          </Button>
        </Space>
      </div>

      {summary && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col xs={24} sm={8}>
            <Card>
              <Statistic
                title="总已用 Credit"
                value={summary.total_used}
                valueStyle={{ color: '#ff4d4f' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card>
              <Statistic
                title="总剩余 Credit"
                value={summary.total_remaining}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card>
              <Statistic title="用户数" value={summary.user_count} />
            </Card>
          </Col>
        </Row>
      )}

      <Table
        dataSource={credits}
        columns={columns}
        rowKey="id"
        loading={loading}
        scroll={{ x: 800 }}
        size="middle"
      />
    </div>
  )
}
