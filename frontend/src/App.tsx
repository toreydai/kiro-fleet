import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Accounts from './pages/Accounts'
import Users from './pages/Users'
import Subscriptions from './pages/Subscriptions'
import Provisioning from './pages/Provisioning'
import Credits from './pages/Credits'
import AccountLogs from './pages/AccountLogs'
import SystemUsers from './pages/SystemUsers'

export default function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/accounts" element={<Accounts />} />
              <Route path="/users" element={<Users />} />
              <Route path="/subscriptions" element={<Subscriptions />} />
              <Route path="/provisioning" element={<Provisioning />} />
              <Route path="/credits" element={<Credits />} />
              <Route path="/logs" element={<AccountLogs />} />
              <Route path="/system-users" element={<SystemUsers />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}
