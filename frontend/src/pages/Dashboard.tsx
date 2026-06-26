import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Table, Tag, Typography, Select, Spin } from 'antd'
import {
  CloudServerOutlined,
  UserOutlined,
  CreditCardOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import { accountsApi } from '../services/accounts'
import type { Account } from '../stores/appStore'
import { ACCOUNT_STATUS_COLOR, ACCOUNT_STATUS_LABEL, fmtDate } from '../lib/utils'

const { Title } = Typography

interface AccountStats {
  total_users: number
  active_subscriptions: number
  total_credits: number
  recent_logs: number
}

export default function Dashboard() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedId, setSelectedId] = useState<number | undefined>(undefined)
  const [stats, setStats] = useState<AccountStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)

  useEffect(() => {
    accountsApi.list().then((res) => {
      const raw = res.data
      const list: Account[] = Array.isArray(raw) ? raw : (raw as { items: Account[] }).items ?? []
      setAccounts(list)
      if (list.length > 0) setSelectedId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setStatsLoading(true)
    accountsApi
      .stats(selectedId)
      .then((res) => setStats(res.data))
      .finally(() => setStatsLoading(false))
  }, [selectedId])

  const columns = [
    { title: '账号名称', dataIndex: 'name', key: 'name' },
    { title: 'SSO 区域', dataIndex: 'sso_region', key: 'sso_region' },
    { title: 'Kiro 区域', dataIndex: 'kiro_region', key: 'kiro_region' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Tag color={ACCOUNT_STATUS_COLOR[s] ?? 'default'}>
          {ACCOUNT_STATUS_LABEL[s] ?? s}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: fmtDate,
    },
  ]

  return (
    <div>
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}
      >
        <Title level={4} style={{ margin: 0 }}>
          账号概览
        </Title>
        <Select
          placeholder="选择 AWS 账号查看统计"
          value={selectedId}
          onChange={setSelectedId}
          style={{ width: 280 }}
          options={accounts.map((a) => ({
            value: a.id,
            label: `${a.name} (${a.sso_region})`,
          }))}
        />
      </div>

      <Spin spinning={statsLoading}>
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={12} md={6}>
            <Card>
              <Statistic
                title="IC 用户数"
                value={stats?.total_users ?? '-'}
                prefix={<UserOutlined />}
                valueStyle={{ color: '#1677ff' }}
              />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card>
              <Statistic
                title="活跃订阅"
                value={stats?.active_subscriptions ?? '-'}
                prefix={<CreditCardOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card>
              <Statistic
                title="Credit 余额"
                value={stats?.total_credits ?? '-'}
                prefix={<BarChartOutlined />}
                valueStyle={{ color: '#faad14' }}
              />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card>
              <Statistic
                title="近期操作"
                value={stats?.recent_logs ?? '-'}
                prefix={<CloudServerOutlined />}
              />
            </Card>
          </Col>
        </Row>
      </Spin>

      <Card title="账号列表">
        <Table
          dataSource={accounts}
          columns={columns}
          rowKey="id"
          size="small"
          pagination={false}
          scroll={{ x: 600 }}
        />
      </Card>
    </div>
  )
}
