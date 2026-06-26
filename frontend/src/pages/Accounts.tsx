import { useEffect, useState } from 'react'
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Tag,
  Space,
  message,
  Popconfirm,
  Typography,
  Tooltip,
  InputNumber,
  Checkbox,
} from 'antd'
import {
  PlusOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  EditOutlined,
  DeleteOutlined,
  DownloadOutlined,
} from '@ant-design/icons'
import { accountsApi } from '../services/accounts'
import type { Account } from '../stores/appStore'
import { ACCOUNT_STATUS_COLOR, ACCOUNT_STATUS_LABEL, fmtDate, extractErrMsg } from '../lib/utils'

const { Title } = Typography
type AccountFormValues = Partial<
  Account & {
    access_key_id: string
    secret_access_key: string
  }
>

export default function Accounts() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editRecord, setEditRecord] = useState<Account | null>(null)
  const [form] = Form.useForm<AccountFormValues>()
  const [submitting, setSubmitting] = useState(false)
  const [actionLoading, setActionLoading] = useState<Record<number, string>>({})

  const load = () => {
    setLoading(true)
    accountsApi
      .list()
      .then((res) => {
        const raw = res.data
        setAccounts(Array.isArray(raw) ? raw : (raw as { items: Account[] }).items ?? [])
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const openAdd = () => {
    setEditRecord(null)
    form.resetFields()
    form.setFieldsValue({
      sso_region: 'us-east-1',
      kiro_region: 'us-east-1',
      sync_interval_minutes: 10,
      is_default: false,
    })
    setModalOpen(true)
  }

  const openEdit = (record: Account) => {
    setEditRecord(record)
    form.setFieldsValue({
      ...record,
      access_key_id: undefined,
      secret_access_key: undefined,
    })
    setModalOpen(true)
  }

  const onSubmit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      if (editRecord) {
        await accountsApi.update(editRecord.id, values)
        void message.success('账号已更新')
      } else {
        await accountsApi.create(values)
        void message.success('账号已创建')
      }
      setModalOpen(false)
      load()
    } catch (e) {
      void message.error(extractErrMsg(e))
    } finally {
      setSubmitting(false)
    }
  }

  const onDelete = async (id: number) => {
    try {
      await accountsApi.delete(id)
      void message.success('已删除')
      load()
    } catch (e) {
      void message.error(extractErrMsg(e, '删除失败'))
    }
  }

  const setAction = (id: number, action: string) =>
    setActionLoading((prev) => ({ ...prev, [id]: action }))
  const clearAction = (id: number) =>
    setActionLoading((prev) => { const next = { ...prev }; delete next[id]; return next })

  const onVerify = async (id: number) => {
    setAction(id, 'verify')
    try {
      await accountsApi.verify(id)
      void message.success('验证成功，账号状态已更新')
      load()
    } catch (e) {
      void message.error(extractErrMsg(e, '验证失败'))
    } finally {
      clearAction(id)
    }
  }

  const onSync = async (id: number) => {
    setAction(id, 'sync')
    try {
      await accountsApi.sync(id)
      void message.success('同步已触发')
    } catch (e) {
      void message.error(extractErrMsg(e, '同步失败'))
    } finally {
      clearAction(id)
    }
  }

  const onExport = async (id: number, name: string) => {
    setAction(id, 'export')
    try {
      const res = await accountsApi.exportJson(id)
      const url = URL.createObjectURL(res.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `kiro-accounts-${name}-${id}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      void message.success('导出成功')
    } catch (e) {
      void message.error(extractErrMsg(e, '导出失败'))
    } finally {
      clearAction(id)
    }
  }

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
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: fmtDate },
    {
      title: '操作',
      key: 'action',
      width: 320,
      render: (_: unknown, record: Account) => (
        <Space size="small" wrap>
          <Tooltip title="连通性验证">
            <Button
              size="small"
              icon={<CheckCircleOutlined />}
              loading={actionLoading[record.id] === 'verify'}
              onClick={() => onVerify(record.id)}
            >
              验证
            </Button>
          </Tooltip>
          <Tooltip title="同步 IC 数据">
            <Button
              size="small"
              icon={<SyncOutlined />}
              loading={actionLoading[record.id] === 'sync'}
              onClick={() => onSync(record.id)}
            >
              同步
            </Button>
          </Tooltip>
          <Tooltip title="导出账号 JSON（用于 kiro-account-manager）">
            <Button
              size="small"
              icon={<DownloadOutlined />}
              loading={actionLoading[record.id] === 'export'}
              onClick={() => onExport(record.id, record.name)}
            >
              导出
            </Button>
          </Tooltip>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该账号？"
            description="删除后所有关联数据将一并清除"
            onConfirm={() => onDelete(record.id)}
            okType="danger"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
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
          AWS 账号管理
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          添加账号
        </Button>
      </div>

      <Table
        dataSource={accounts}
        columns={columns}
        rowKey="id"
        loading={loading}
        scroll={{ x: 800 }}
      />

      <Modal
        title={editRecord ? '编辑账号' : '添加账号'}
        open={modalOpen}
        onOk={onSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="账号名称"
            rules={[{ required: true, message: '请输入账号名称' }]}
          >
            <Input placeholder="如：生产账号 - us-east-1" />
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
          >
            <Input.TextArea placeholder="可选" rows={2} />
          </Form.Item>
          <Form.Item
            name="access_key_id"
            label="Access Key ID"
            rules={[{ required: !editRecord, message: '请输入 Access Key ID' }]}
          >
            <Input placeholder="AKIA..." autoComplete="off" />
          </Form.Item>
          <Form.Item
            name="secret_access_key"
            label="Secret Access Key"
            rules={[{ required: !editRecord, message: '请输入 Secret Access Key' }]}
            extra={editRecord ? '留空则不更新现有密钥' : undefined}
          >
            <Input.Password placeholder="Secret Access Key" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="sso_region"
            label="SSO 区域"
            rules={[{ required: true, message: '请输入 SSO 区域' }]}
          >
            <Input placeholder="us-east-1" />
          </Form.Item>
          <Form.Item
            name="kiro_region"
            label="Kiro 区域"
            rules={[{ required: true, message: '请输入 Kiro 区域' }]}
          >
            <Input placeholder="us-east-1" />
          </Form.Item>
          <Form.Item
            name="instance_arn"
            label="SSO Instance ARN"
            rules={[{ required: true, message: '请输入 SSO Instance ARN' }]}
          >
            <Input placeholder="arn:aws:sso:::instance/ssoins-..." />
          </Form.Item>
          <Form.Item
            name="identity_store_id"
            label="Identity Store ID"
            rules={[{ required: true, message: '请输入 Identity Store ID' }]}
          >
            <Input placeholder="d-xxxxxxxxxx" />
          </Form.Item>
          <Form.Item
            name="kiro_login_url"
            label="Kiro 登录 URL"
          >
            <Input placeholder="https://d-xxxxxxxxxx.awsapps.com/start" />
          </Form.Item>
          <Form.Item
            name="sync_interval_minutes"
            label="同步间隔（分钟）"
            rules={[{ required: true, message: '请输入同步间隔' }]}
          >
            <InputNumber min={1} max={1440} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_default" valuePropName="checked">
            <Checkbox>设为默认账号</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
