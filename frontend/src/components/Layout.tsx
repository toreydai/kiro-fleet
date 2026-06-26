import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  Layout as AntLayout,
  Menu,
  Button,
  Avatar,
  Dropdown,
  Grid,
  Typography,
} from 'antd'
import {
  DashboardOutlined,
  CloudServerOutlined,
  UserOutlined,
  CreditCardOutlined,
  ThunderboltOutlined,
  BarChartOutlined,
  FileTextOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '../stores/authStore'

const { Sider, Header, Content } = AntLayout
const { useBreakpoint } = Grid

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '概览' },
  { key: '/accounts', icon: <CloudServerOutlined />, label: '账号管理' },
  { key: '/users', icon: <UserOutlined />, label: '用户管理' },
  { key: '/subscriptions', icon: <CreditCardOutlined />, label: '订阅管理' },
  { key: '/provisioning', icon: <ThunderboltOutlined />, label: '批量开通' },
  { key: '/credits', icon: <BarChartOutlined />, label: 'Credit 用量' },
  { key: '/logs', icon: <FileTextOutlined />, label: '操作日志' },
  { key: '/system-users', icon: <SettingOutlined />, label: '系统用户' },
]

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const screens = useBreakpoint()
  const { user, logout } = useAuthStore()

  const isMobile = !screens.md

  const userMenu = {
    items: [
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        danger: true,
      },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'logout') logout()
    },
  }

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={isMobile ? true : collapsed}
        collapsedWidth={isMobile ? 0 : 80}
        style={{ background: '#001529', position: 'fixed', height: '100vh', zIndex: 100 }}
        width={220}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <Typography.Text
            style={{
              color: '#fff',
              fontWeight: 700,
              fontSize: collapsed || isMobile ? 14 : 18,
              letterSpacing: 1,
            }}
          >
            {collapsed || isMobile ? 'KF' : 'Kiro Fleet'}
          </Typography.Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ marginTop: 8 }}
        />
      </Sider>

      <AntLayout
        style={{
          marginLeft: isMobile ? 0 : collapsed ? 80 : 220,
          transition: 'margin-left 0.2s',
        }}
      >
        <Header
          style={{
            padding: '0 16px',
            background: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,21,41,0.08)',
            position: 'sticky',
            top: 0,
            zIndex: 99,
          }}
        >
          <Button
            type="text"
            icon={collapsed || isMobile ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            size="large"
          />
          <Dropdown menu={userMenu} placement="bottomRight">
            <div
              style={{
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '4px 8px',
                borderRadius: 6,
              }}
            >
              <Avatar
                size="small"
                style={{ backgroundColor: '#1677ff' }}
                icon={<UserOutlined />}
              />
              <Typography.Text>{user?.username ?? '用户'}</Typography.Text>
            </div>
          </Dropdown>
        </Header>

        <Content style={{ margin: 16, padding: 24, background: '#fff', borderRadius: 8, minHeight: 280 }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  )
}
