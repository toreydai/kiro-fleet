import { useEffect, useState, useCallback } from 'react'
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Space,
  message,
  Popconfirm,
  Typography,
  Tag,
} from 'antd'
import {
  PlusOutlined,
  MailOutlined,
  KeyOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { usersApi, type IcUser } from '../services/users'
import { accountsApi } from '../services/accounts'
import type { Account } from '../stores/appStore'
import { fmtDate, extractErrMsg } from '../lib/utils'

const { Title } = Typography

export default function Users() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | undefined>(undefined)
  const [users, setUsers] = useState<IcUser[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editRecord, setEditRecord] = useState<IcUser | null>(null)
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    accountsApi.list().then((res) => {
      const raw = res.data
      const list: Account[] = Array.isArray(raw) ? raw : (raw as { items: Account[] }).items ?? []
      setAccounts(list)
      if (list.length > 0) setSelectedAccountId(list[0].id)
    })
  }, [])

  const loadUsers = useCallback(() => {
    if (!selectedAccountId) return
    setLoading(true)
    usersApi
      .list(selectedAccountId)
      .then((res) => {
        const raw = res.data
        setUsers(Array.isArray(raw) ? raw : (raw as { items: IcUser[] }).items ?? [])
      })
      .finally(() => setLoading(false))
  }, [selectedAccountId])

  useEffect(() => {
    loadUsers()
  }, [loadUsers])

  const openAdd = () => {
    setEditRecord(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (record: IcUser) => {
    setEditRecord(record)
    form.setFieldsValue({
      username: record.username,
      email: record.email,
      display_name: record.display_name,
    })
    setModalOpen(true)
  }

  const onSubmit = async () => {
    if (!selectedAccountId) return
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      if (editRecord) {
        await usersApi.update(selectedAccountId, editRecord.id, values)
        void message.success('用户已更新')
      } else {
        await usersApi.create(selectedAccountId, values)
        void message.success('用户已创建')
      }
      setModalOpen(false)
      loadUsers()
    } catch (e) {
      void message.error(extractErrMsg(e))
    } finally {
      setSubmitting(false)
    }
  }

  const onDelete = async (uid: string) => {
    if (!selectedAccountId) return
    try {
      await usersApi.delete(selectedAccountId, uid)
      void message.success('已删除')
      loadUsers()
    } catch (e) {
      void message.error(extractErrMsg(e, '删除失败'))
    }
  }

  const onResetPassword = async (uid: string) => {
    if (!selectedAccountId) return
    try {
      const res = await usersApi.resetPassword(selectedAccountId, uid)
      const pwd = res.data.temporary_password ?? res.data.new_password
      Modal.success({
        title: '密码重置成功',
        content: pwd
          ? `临时密码：${pwd}（请告知用户尽快修改）`
          : '重置邮件已发送至用户邮箱',
      })
    } catch (e) {
      void message.error(extractErrMsg(e, '重置密码失败'))
    }
  }

  const onVerifyEmail = async (uid: string) => {
    if (!selectedAccountId) return
    try {
      await usersApi.verifyEmail(selectedAccountId, uid)
      void message.success('邮箱验证邮件已发送')
    } catch (e) {
      void message.error(extractErrMsg(e, '操作失败'))
    }
  }

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    { title: '显示名称', dataIndex: 'display_name', key: 'display_name' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s?: string) =>
        s ? (
          <Tag color={s === 'active' ? 'green' : 'orange'}>{s}</Tag>
        ) : (
          '-'
        ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: fmtDate,
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      render: (_: unknown, record: IcUser) => (
        <Space size="small" wrap>
          <Button
            size="small"
            icon={<MailOutlined />}
            onClick={() => onVerifyEmail(record.id)}
          >
            验证邮箱
          </Button>
          <Button
            size="small"
            icon={<KeyOutlined />}
            onClick={() => onResetPassword(record.id)}
          >
            重置密码
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该 IC 用户？"
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
          IC 用户管理
        </Title>
        <Space>
          <Select
            placeholder="选择 AWS 账号"
            value={selectedAccountId}
            onChange={setSelectedAccountId}
            style={{ width: 240 }}
            options={accounts.map((a) => ({ value: a.id, label: `${a.name}` }))}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={openAdd}
            disabled={!selectedAccountId}
          >
            新建用户
          </Button>
        </Space>
      </div>

      <Table
        dataSource={users}
        columns={columns}
        rowKey="id"
        loading={loading}
        scroll={{ x: 800 }}
      />

      <Modal
        title={editRecord ? '编辑用户' : '新建 IC 用户'}
        open={modalOpen}
        onOk={onSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          {!editRecord && (
            <Form.Item
              name="username"
              label="用户名"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input placeholder="如：kiro_001" />
            </Form.Item>
          )}
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效邮箱地址' },
            ]}
          >
            <Input placeholder="user@example.com" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称">
            <Input placeholder="可选，不填则使用用户名" />
          </Form.Item>
          {!editRecord && (
            <Form.Item name="password" label="初始密码">
              <Input.Password placeholder="留空则自动生成临时密码" />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  )
}
