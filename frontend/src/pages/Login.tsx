import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Card, message, Typography } from 'antd'
import { UserOutlined, LockOutlined, SafetyOutlined } from '@ant-design/icons'
import { authApi } from '../services/auth'
import { useAuthStore } from '../stores/authStore'
import { extractErrMsg } from '../lib/utils'

const { Title } = Typography

type Step = 'login' | 'mfa'

export default function Login() {
  const navigate = useNavigate()
  const { setTokens, setUser } = useAuthStore()
  const [step, setStep] = useState<Step>('login')
  const [preAuthToken, setPreAuthToken] = useState('')
  const [loading, setLoading] = useState(false)

  const onLogin = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const res = await authApi.login(values.username, values.password)
      const data = res.data
      if (data.requires_mfa && data.pre_auth_token) {
        setPreAuthToken(data.pre_auth_token)
        setStep('mfa')
      } else if (data.access_token && data.refresh_token) {
        setTokens(data.access_token, data.refresh_token)
        const meRes = await authApi.me()
        setUser(meRes.data)
        navigate('/dashboard')
      }
    } catch (e) {
      void message.error(extractErrMsg(e, '登录失败，请检查用户名和密码'))
    } finally {
      setLoading(false)
    }
  }

  const onMfa = async (values: { code: string }) => {
    setLoading(true)
    try {
      const res = await authApi.mfaVerify(preAuthToken, values.code)
      const { access_token, refresh_token } = res.data
      setTokens(access_token, refresh_token)
      const meRes = await authApi.me()
      setUser(meRes.data)
      navigate('/dashboard')
    } catch {
      void message.error('MFA 验证失败，请检查验证码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}
    >
      <Card style={{ width: 380, boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={3} style={{ margin: 0 }}>
            Kiro Fleet
          </Title>
          <Typography.Text type="secondary">
            AWS Identity Center 管理平台
          </Typography.Text>
        </div>

        {step === 'login' ? (
          <Form onFinish={onLogin} layout="vertical" autoComplete="off">
            <Form.Item
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input
                prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
                placeholder="用户名"
                size="large"
              />
            </Form.Item>
            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
                placeholder="密码"
                size="large"
              />
            </Form.Item>
            <Form.Item style={{ marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
              >
                登录
              </Button>
            </Form.Item>
          </Form>
        ) : (
          <Form onFinish={onMfa} layout="vertical">
            <Typography.Paragraph type="secondary">
              请输入验证器 App 中的 6 位 MFA 验证码
            </Typography.Paragraph>
            <Form.Item
              name="code"
              rules={[{ required: true, message: '请输入验证码' }]}
            >
              <Input
                prefix={<SafetyOutlined style={{ color: '#bfbfbf' }} />}
                placeholder="6 位验证码"
                size="large"
                maxLength={6}
              />
            </Form.Item>
            <Form.Item style={{ marginBottom: 8 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
              >
                验证
              </Button>
            </Form.Item>
            <Button type="link" onClick={() => setStep('login')} block>
              返回登录
            </Button>
          </Form>
        )}
      </Card>
    </div>
  )
}
