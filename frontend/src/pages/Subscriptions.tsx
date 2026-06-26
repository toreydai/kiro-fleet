import { useEffect, useState, useCallback } from 'react'
import {
  Table,
  Button,
  Select,
  Space,
  Tag,
  Typography,
  Tabs,
  Modal,
  Form,
  message,
  Popconfirm,
  type TableRowSelection,
} from 'antd'
import { SwapOutlined, DeleteOutlined } from '@ant-design/icons'
import { subscriptionsApi, type Subscription } from '../services/subscriptions'
import { accountsApi } from '../services/accounts'
import type { Account } from '../stores/appStore'
import { fmtDate, subLabel, SUB_LABEL, extractErrMsg } from '../lib/utils'

const { Title } = Typography

const planOptions = Object.entries(SUB_LABEL).map(([value, label]) => ({
  value,
  label,
}))

export default function Subscriptions() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | undefined>(undefined)
  const [subs, setSubs] = useState<Subscription[]>([])
  const [canceledSubs, setCanceledSubs] = useState<Subscription[]>([])
  const [allSubs, setAllSubs] = useState<Subscription[]>([])
  const [loading, setLoading] = useState(false)

  const [changePlanModal, setChangePlanModal] = useState<{
    open: boolean
    sub?: Subscription
  }>({ open: false })
  const [changePlanForm] = Form.useForm<{ plan: string }>()

  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [bulkPlanModal, setBulkPlanModal] = useState(false)
  const [bulkForm] = Form.useForm<{ plan: string }>()

  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    accountsApi.list().then((res) => {
      const raw = res.data
      const list: Account[] = Array.isArray(raw) ? raw : (raw as { items: Account[] }).items ?? []
      setAccounts(list)
      if (list.length > 0) setSelectedAccountId(list[0].id)
    })
    subscriptionsApi.listAll().then((res) => {
      const raw = res.data
      setAllSubs(Array.isArray(raw) ? raw : (raw as { items: Subscription[] }).items ?? [])
    })
  }, [])

  const loadSubs = useCallback(() => {
    if (!selectedAccountId) return
    setLoading(true)
    Promise.all([
      subscriptionsApi.list(selectedAccountId),
      subscriptionsApi.listCanceled(selectedAccountId),
    ])
      .then(([r1, r2]) => {
        const s1 = r1.data
        const s2 = r2.data
        setSubs(Array.isArray(s1) ? s1 : (s1 as { items: Subscription[] }).items ?? [])
        setCanceledSubs(Array.isArray(s2) ? s2 : (s2 as { items: Subscription[] }).items ?? [])
      })
      .finally(() => setLoading(false))
  }, [selectedAccountId])

  useEffect(() => {
    loadSubs()
    setSelectedRowKeys([])
  }, [loadSubs])

  const onCancel = async (sid: string) => {
    if (!selectedAccountId) return
    try {
      await subscriptionsApi.cancel(selectedAccountId, sid)
      void message.success('订阅已取消')
      loadSubs()
    } catch (e) {
      void message.error(extractErrMsg(e, '取消失败'))
    }
  }

  const openChangePlan = (sub: Subscription) => {
    setChangePlanModal({ open: true, sub })
    changePlanForm.setFieldsValue({ plan: sub.plan })
  }

  const submitChangePlan = async () => {
    if (!selectedAccountId || !changePlanModal.sub) return
    const values = await changePlanForm.validateFields()
    setSubmitting(true)
    try {
      await subscriptionsApi.changePlan(selectedAccountId, changePlanModal.sub.id, values)
      void message.success('套餐已变更')
      setChangePlanModal({ open: false })
      loadSubs()
    } catch (e) {
      void message.error(extractErrMsg(e, '变更失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const submitBulkPlan = async () => {
    const values = await bulkForm.validateFields()
    setSubmitting(true)
    try {
      await subscriptionsApi.changePlanBulk({
        subscription_ids: selectedRowKeys as string[],
        new_plan: values.plan,
      })
      void message.success(`已批量变更 ${selectedRowKeys.length} 条订阅`)
      setBulkPlanModal(false)
      bulkForm.resetFields()
      setSelectedRowKeys([])
      loadSubs()
    } catch (e) {
      void message.error(extractErrMsg(e, '批量变更失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const subColumns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '套餐',
      dataIndex: 'plan',
      key: 'plan',
      render: (p: string) => <Tag color="blue">{subLabel(p)}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Tag color={s === 'active' ? 'green' : 'orange'}>{s}</Tag>
      ),
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: fmtDate },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: unknown, record: Subscription) => (
        <Space size="small">
          <Button
            size="small"
            icon={<SwapOutlined />}
            onClick={() => openChangePlan(record)}
          >
            变更套餐
          </Button>
          <Popconfirm
            title="确定取消该订阅？"
            onConfirm={() => onCancel(record.id)}
            okType="danger"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              取消
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const canceledColumns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '套餐',
      dataIndex: 'plan',
      key: 'plan',
      render: (p: string) => <Tag>{subLabel(p)}</Tag>,
    },
    {
      title: '取消时间',
      dataIndex: 'canceled_at',
      key: 'canceled_at',
      render: fmtDate,
    },
  ]

  const allColumns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '套餐',
      dataIndex: 'plan',
      key: 'plan',
      render: (p: string) => <Tag color="blue">{subLabel(p)}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Tag color={s === 'active' ? 'green' : 'orange'}>{s}</Tag>
      ),
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: fmtDate },
  ]

  const rowSelection: TableRowSelection<Subscription> = {
    selectedRowKeys,
    onChange: (keys) => setSelectedRowKeys(keys),
  }

  const accountSelector = (
    <Select
      placeholder="选择 AWS 账号"
      value={selectedAccountId}
      onChange={(v) => setSelectedAccountId(v)}
      style={{ width: 240 }}
      options={accounts.map((a) => ({ value: a.id, label: a.name }))}
    />
  )

  const items = [
    {
      key: 'account',
      label: '本账号订阅',
      children: (
        <>
          <Space style={{ marginBottom: 12 }} wrap>
            {accountSelector}
            {selectedRowKeys.length > 0 && (
              <Button
                icon={<SwapOutlined />}
                onClick={() => setBulkPlanModal(true)}
              >
                批量变更套餐（{selectedRowKeys.length}）
              </Button>
            )}
          </Space>
          <Table
            dataSource={subs}
            columns={subColumns}
            rowKey="id"
            loading={loading}
            rowSelection={rowSelection}
            scroll={{ x: 800 }}
          />
        </>
      ),
    },
    {
      key: 'canceled',
      label: '已取消订阅',
      children: (
        <>
          <div style={{ marginBottom: 12 }}>{accountSelector}</div>
          <Table
            dataSource={canceledSubs}
            columns={canceledColumns}
            rowKey="id"
            loading={loading}
            scroll={{ x: 700 }}
          />
        </>
      ),
    },
    {
      key: 'all',
      label: '全局总览',
      children: (
        <Table
          dataSource={allSubs}
          columns={allColumns}
          rowKey="id"
          scroll={{ x: 800 }}
        />
      ),
    },
  ]

  return (
    <div>
      <Title level={4}>订阅管理</Title>
      <Tabs items={items} />

      {/* 单条变更套餐 */}
      <Modal
        title="变更套餐"
        open={changePlanModal.open}
        onOk={submitChangePlan}
        onCancel={() => setChangePlanModal({ open: false })}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={changePlanForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="plan"
            label="新套餐"
            rules={[{ required: true, message: '请选择套餐' }]}
          >
            <Select options={planOptions} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 批量变更套餐 */}
      <Modal
        title={`批量变更套餐（已选 ${selectedRowKeys.length} 条）`}
        open={bulkPlanModal}
        onOk={submitBulkPlan}
        onCancel={() => setBulkPlanModal(false)}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={bulkForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="plan"
            label="目标套餐"
            rules={[{ required: true, message: '请选择目标套餐' }]}
          >
            <Select options={planOptions} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
