import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  List,
  Progress,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  message,
  Divider,
} from 'antd'
import {
  ThunderboltOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  StopOutlined,
} from '@ant-design/icons'
import { accountsApi } from '../services/accounts'
import {
  streamProvisioning,
  provisioningApi,
  type ProvisioningStreamEvent,
} from '../services/provisioning'
import type { Account } from '../stores/appStore'
import { subLabel } from '../lib/utils'

const { Title, Text } = Typography

interface UserResult {
  username: string
  email?: string
  plan?: string
  password?: string
  status: 'success' | 'failed'
  error?: string
}

type RunState = 'idle' | 'running' | 'done' | 'error'

interface FormValues {
  prefix: string
  domain: string
  group_id?: string
  power_count: number
  pro_max_count: number
  pro_plus_count: number
  pro_count: number
}

interface IcGroup {
  GroupId: string
  DisplayName: string
}

export default function Provisioning() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | undefined>(undefined)
  const [groups, setGroups] = useState<IcGroup[]>([])
  const [form] = Form.useForm<FormValues>()

  const [runState, setRunState] = useState<RunState>('idle')
  const [total, setTotal] = useState(0)
  const [done, setDone] = useState(0)
  const [userResults, setUserResults] = useState<UserResult[]>([])
  const [taskId, setTaskId] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    accountsApi.list().then((res) => {
      const raw = res.data
      const list: Account[] = Array.isArray(raw) ? raw : (raw as { items: Account[] }).items ?? []
      setAccounts(list)
      if (list.length > 0) setSelectedAccountId(list[0].id)
    })
  }, [])

  // 账号切换时重新拉 Group 列表
  useEffect(() => {
    if (!selectedAccountId) return
    import('../lib/axios').then(({ default: api }) => {
      api.get<{ groups: IcGroup[] }>(`/accounts/${selectedAccountId}/users/groups`)
        .then((res) => setGroups(res.data.groups ?? []))
        .catch(() => setGroups([]))
    })
  }, [selectedAccountId])

  // 新结果出现时自动滚动到底部
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [userResults])

  const onStart = async () => {
    if (!selectedAccountId) {
      void message.warning('请先选择 AWS 账号')
      return
    }
    const values = await form.validateFields()
    const { prefix, domain, group_id, power_count, pro_max_count, pro_plus_count, pro_count } = values

    if (!power_count && !pro_max_count && !pro_plus_count && !pro_count) {
      void message.warning('请至少填写一种套餐的开通数量')
      return
    }

    // 重置状态
    setRunState('running')
    setUserResults([])
    setDone(0)
    setTotal((power_count ?? 0) + (pro_max_count ?? 0) + (pro_plus_count ?? 0) + (pro_count ?? 0))
    setTaskId(null)
    setErrorMsg(null)

    const payload = {
      prefix: prefix ?? 'kiro',
      domain: domain ?? '',
      ...(group_id ? { group_id } : {}),
      plans: [
        ...(power_count
          ? [{ subscription_type: 'KIRO_ENTERPRISE_PRO_POWER', count: power_count }]
          : []),
        ...(pro_max_count
          ? [{ subscription_type: 'KIRO_ENTERPRISE_PRO_MAX', count: pro_max_count }]
          : []),
        ...(pro_plus_count
          ? [{ subscription_type: 'KIRO_ENTERPRISE_PRO_PLUS', count: pro_plus_count }]
          : []),
        ...(pro_count
          ? [{ subscription_type: 'KIRO_ENTERPRISE_PRO', count: pro_count }]
          : []),
      ],
    }

    const ctrl = await streamProvisioning(
      selectedAccountId,
      payload,
      (event: ProvisioningStreamEvent) => {
        switch (event.type) {
          case 'progress':
            if (event.total !== undefined) setTotal(event.total)
            if (event.done !== undefined) setDone(event.done)
            break

          case 'user_created':
            setUserResults((prev) => [
              ...prev,
              {
                username: event.username ?? '',
                email: event.email,
                plan: event.plan,
                password: event.password,
                status: 'success',
              },
            ])
            setDone((d) => d + 1)
            break

          case 'user_failed':
            setUserResults((prev) => [
              ...prev,
              {
                username: event.username ?? '',
                email: event.email,
                plan: event.plan,
                status: 'failed',
                error: event.error,
              },
            ])
            setDone((d) => d + 1)
            break

          case 'summary':
            if (event.task_id) setTaskId(event.task_id)
            break

          case 'error':
            setErrorMsg(event.error ?? '未知错误')
            setRunState('error')
            break
        }
      },
      () => {
        setRunState('done')
        void message.success('批量开通已完成！')
      },
      (err: Error) => {
        setErrorMsg(err.message)
        setRunState('error')
        void message.error('批量开通中断：' + err.message)
      },
    )
    abortRef.current = ctrl
  }

  const onStop = () => {
    abortRef.current?.abort()
    setRunState('idle')
    void message.warning('已手动停止')
  }

  const onExport = async () => {
    if (!selectedAccountId || !taskId) return
    try {
      const res = await provisioningApi.exportJson(selectedAccountId, taskId)
      const blob = res.data as Blob
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `kiro-accounts-${taskId}.json`
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      URL.revokeObjectURL(url)
    } catch {
      void message.error('导出失败')
    }
  }

  const percent = total > 0 ? Math.round((done / total) * 100) : 0
  const successCount = userResults.filter((r) => r.status === 'success').length
  const failCount = userResults.filter((r) => r.status === 'failed').length

  return (
    <div>
      <Title level={4}>
        <ThunderboltOutlined /> 一键批量开通
      </Title>

      <Row gutter={[16, 16]}>
        {/* ── 左侧：配置区 ── */}
        <Col xs={24} lg={10}>
          <Card title="开通配置" bordered>
            <Form
              form={form}
              layout="vertical"
              initialValues={{ prefix: 'kiro', domain: '', group_id: undefined, power_count: 0, pro_max_count: 0, pro_plus_count: 0, pro_count: 0 }}
            >
              {/* 账号选择 */}
              <Form.Item label="目标 AWS 账号" required>
                <Select
                  value={selectedAccountId}
                  onChange={setSelectedAccountId}
                  placeholder="请选择账号"
                  options={accounts.map((a) => ({
                    value: a.id,
                    label: `${a.name}  (${a.sso_region})`,
                  }))}
                />
              </Form.Item>

              {/* 用户名前缀 */}
              <Form.Item
                name="prefix"
                label="用户名前缀"
                rules={[
                  { required: true, message: '请输入前缀' },
                  { pattern: /^[a-z0-9_-]+$/, message: '只允许小写字母、数字、下划线、连字符' },
                ]}
                extra="生成用户名格式：前缀_001, 前缀_002 …"
              >
                <Input placeholder="如：kiro" maxLength={20} />
              </Form.Item>

              {/* 邮箱域名 */}
              <Form.Item
                name="domain"
                label="邮箱域名"
                rules={[{ required: true, message: '请输入邮箱域名' }]}
                extra="用于生成用户邮箱，如：example.com"
              >
                <Input placeholder="如：example.com" />
              </Form.Item>

              {/* IDC Group */}
              <Form.Item
                name="group_id"
                label="加入用户组（可选）"
                extra="开通后自动将用户加入所选 IDC Group"
              >
                <Select
                  allowClear
                  placeholder="不指定用户组"
                  options={groups.map((g) => ({
                    value: g.GroupId,
                    label: g.DisplayName,
                  }))}
                />
              </Form.Item>

              <Divider orientation="left" plain>套餐配置</Divider>

              {/* Power 套餐 */}
              <Card
                size="small"
                title={<Tag color="purple">Power 套餐 $200/月</Tag>}
                style={{ marginBottom: 12 }}
              >
                <Form.Item name="power_count" label="开通数量" style={{ marginBottom: 0 }}>
                  <InputNumber min={0} max={500} style={{ width: '100%' }} />
                </Form.Item>
              </Card>

              {/* Pro Max 套餐 */}
              <Card
                size="small"
                title={<Tag color="volcano">Pro Max 套餐 $100/月</Tag>}
                style={{ marginBottom: 12 }}
              >
                <Form.Item name="pro_max_count" label="开通数量" style={{ marginBottom: 0 }}>
                  <InputNumber min={0} max={500} style={{ width: '100%' }} />
                </Form.Item>
              </Card>

              {/* Pro+ 套餐 */}
              <Card
                size="small"
                title={<Tag color="geekblue">Pro+ 套餐 $40/月</Tag>}
                style={{ marginBottom: 12 }}
              >
                <Form.Item name="pro_plus_count" label="开通数量" style={{ marginBottom: 0 }}>
                  <InputNumber min={0} max={500} style={{ width: '100%' }} />
                </Form.Item>
              </Card>

              {/* Pro 套餐 */}
              <Card size="small" title={<Tag color="blue">Pro 套餐 $20/月</Tag>}>
                <Form.Item name="pro_count" label="开通数量" style={{ marginBottom: 0 }}>
                  <InputNumber min={0} max={500} style={{ width: '100%' }} />
                </Form.Item>
              </Card>
            </Form>

            <Space style={{ marginTop: 20 }}>
              <Button
                type="primary"
                size="large"
                icon={<ThunderboltOutlined />}
                onClick={onStart}
                loading={runState === 'running'}
                disabled={runState === 'running'}
              >
                开始开通
              </Button>
              {runState === 'running' && (
                <Button
                  size="large"
                  danger
                  icon={<StopOutlined />}
                  onClick={onStop}
                >
                  停止
                </Button>
              )}
            </Space>
          </Card>
        </Col>

        {/* ── 右侧：进度区 ── */}
        <Col xs={24} lg={14}>
          <Card
            title="实时开通进度"
            extra={
              runState === 'done' && taskId ? (
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  onClick={onExport}
                >
                  导出 JSON
                </Button>
              ) : null
            }
            bordered
          >
            {/* 空闲状态 */}
            {runState === 'idle' && (
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <ThunderboltOutlined
                  style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 12, display: 'block' }}
                />
                <Text type="secondary">填写左侧配置后点击"开始开通"</Text>
              </div>
            )}

            {/* 运行中 / 完成 */}
            {(runState === 'running' || runState === 'done') && (
              <>
                {/* 进度条 */}
                <div style={{ marginBottom: 16 }}>
                  <Progress
                    percent={percent}
                    status={runState === 'done' ? 'success' : 'active'}
                    format={() => `${done} / ${total}`}
                    strokeWidth={12}
                  />
                  <Space style={{ marginTop: 8 }} wrap>
                    <Tag color="green">成功 {successCount}</Tag>
                    <Tag color="red">失败 {failCount}</Tag>
                    {runState === 'running' && (
                      <Tag color="processing" icon={<LoadingOutlined />}>
                        处理中…
                      </Tag>
                    )}
                    {runState === 'done' && (
                      <Tag color="success" icon={<CheckCircleOutlined />}>
                        已完成
                      </Tag>
                    )}
                  </Space>
                </div>

                {/* 用户结果列表 */}
                <div
                  ref={listRef}
                  style={{ maxHeight: 420, overflowY: 'auto', border: '1px solid #f0f0f0', borderRadius: 6 }}
                >
                  <List
                    size="small"
                    dataSource={userResults}
                    renderItem={(item) => (
                      <List.Item
                        style={{
                          padding: '8px 12px',
                          background: item.status === 'failed'
                            ? '#fff2f0'
                            : item.status === 'success'
                            ? '#f6ffed'
                            : 'transparent',
                        }}
                        extra={
                          item.status === 'success' ? (
                            <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
                          ) : (
                            <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 16 }} />
                          )
                        }
                      >
                        <List.Item.Meta
                          title={
                            <Space size={6}>
                              <Text strong style={{ fontSize: 13 }}>{item.username}</Text>
                              {item.plan && (
                                <Tag
                                  color={item.plan.includes('POWER') ? 'purple' : item.plan.includes('MAX') ? 'volcano' : item.plan.includes('PLUS') ? 'geekblue' : 'blue'}
                                  style={{ fontSize: 11, margin: 0 }}
                                >
                                  {subLabel(item.plan)}
                                </Tag>
                              )}
                            </Space>
                          }
                          description={
                            item.status === 'failed' && item.error ? (
                              <Text type="danger" style={{ fontSize: 12 }}>
                                {item.error}
                              </Text>
                            ) : (
                              <div style={{ fontSize: 12, lineHeight: '20px' }}>
                                <div><Text type="secondary">{item.email ?? ''}</Text></div>
                                {item.password && (
                                  <div>
                                    <Text type="secondary" style={{ marginRight: 4 }}>密码：</Text>
                                    <Text copyable={{ text: item.password }} style={{ fontFamily: 'monospace' }}>
                                      {item.password}
                                    </Text>
                                  </div>
                                )}
                              </div>
                            )
                          }
                        />
                      </List.Item>
                    )}
                  />
                </div>
              </>
            )}

            {/* 错误状态 */}
            {runState === 'error' && errorMsg && (
              <Alert
                type="error"
                message="批量开通失败"
                description={errorMsg}
                showIcon
                action={
                  <Button size="small" onClick={() => setRunState('idle')}>
                    关闭
                  </Button>
                }
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
