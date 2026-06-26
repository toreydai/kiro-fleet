import { useEffect, useState } from 'react'
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
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import api from '../lib/axios'
import { fmtDate, extractErrMsg } from '../lib/utils'

const { Title } = Typography

interface SystemUser {
  id: number
  username: string
  email: string
  role: string
  is_active?: boolean
  created_at: string
}

interface CreateUserForm {
  username: string
  email: string
  password: string
  role: string
}

export default function SystemUsers() {
  const [users, setUsers] = useState<SystemUser[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm<CreateUserForm>()
  const [submitting, setSubmitting] = useState(false)

  const load = () => {
    setLoading(true)
    api
      .get<{ items: SystemUser[] } | SystemUser[]>('/auth/users')
      .then((res) => {
        const raw = res.data
        setUsers(Array.isArray(raw) ? raw : (raw as { items: SystemUser[] }).items ?? [])
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const openAdd = () => {
    form.resetFields()
    form.setFieldValue('role', 'operator')
    setModalOpen(true)
  }

  const onSubmit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      await api.post('/auth/users', values)
      void message.success('系统用户已创建')
      setModalOpen(false)
      load()
    } catch (e) {
      void message.error(extractErrMsg(e, '创建失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const onDelete = async (id: number) => {
    try {
      await api.delete(`/auth/users/${id}`)
      void message.success('已删除')
      load()
    } catch (e) {
      void message.error(extractErrMsg(e, '删除失败'))
    }
  }

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (r: string) => (
        <Tag color={r === 'admin' ? 'red' : 'blue'}>
          {r === 'admin' ? '管理员' : '操作员'}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (v?: boolean) => (
        <Tag color={v !== false ? 'green' : 'orange'}>
          {v !== false ? '启用' : '禁用'}
        </Tag>
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
      render: (_: unknown, record: SystemUser) => (
        <Popconfirm
          title="确定删除该系统用户？"
          description="此操作不可撤销"
          onConfirm={() => onDelete(record.id)}
          okType="danger"
        >
          <Button size="small" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
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
          系统用户管理
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          新建用户
        </Button>
      </div>

      <Table
        dataSource={users}
        columns={columns}
        rowKey="id"
        loading={loading}
      />

      <Modal
        title="新建系统用户"
        open={modalOpen}
        onOk={onSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input placeholder="字母、数字、下划线" />
          </Form.Item>
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效邮箱地址' },
            ]}
          >
            <Input placeholder="admin@example.com" />
          </Form.Item>
          <Form.Item
            name="password"
            label="初始密码"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, message: '密码长度不少于 8 位' },
            ]}
          >
            <Input.Password placeholder="至少 8 位" />
          </Form.Item>
          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true }]}
          >
            <Select
              options={[
                { value: 'admin', label: '管理员（全权限）' },
                { value: 'operator', label: '操作员（只读 + 有限操作）' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
