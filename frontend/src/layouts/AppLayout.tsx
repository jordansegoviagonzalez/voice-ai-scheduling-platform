import {
  Activity,
  CalendarDays,
  ClipboardList,
  LayoutDashboard,
  Route,
  Stethoscope,
  MessageSquare,
  Users,
  LogOut
} from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const navigation = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/calls', label: 'Calls', icon: ClipboardList },
  { to: '/appointments', label: 'Appointments', icon: CalendarDays },
  { to: '/physicians', label: 'Physicians', icon: Stethoscope },
  { to: '/routing-audit', label: 'Routing Audit', icon: Route },
  { to: '/simulator', label: 'Call Simulator', icon: Activity },
  { to: '/web-chat-sessions', label: 'Web Chat Sessions', icon: MessageSquare },
  { to: '/patients', label: 'Patients', icon: Users },
];

export function AppLayout() {
  const { user, logout } = useAuth();

  // Extract initials if name exists
  const getInitials = (name: string) => {
    return name
      .replace(/^Dr\.\s+/i, '')
      .split(' ')
      .map(n => n[0])
      .join('')
      .substring(0, 2)
      .toUpperCase();
  };

  const initials = user?.name ? getInitials(user.name) : 'A';
  const roleDisplay = user?.role === 'admin_provider' ? 'Administrator' : user?.role || 'Administrator';

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><Activity size={25} /></span>
          <div><strong>Voice AI Scheduling Platform</strong><small>Operations console</small></div>
        </div>
        <nav aria-label="Primary navigation">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
              <Icon size={19} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className="status-dot" />
          <div><strong>Core services online</strong><small>API · Routing · Database</small></div>
        </div>
        <div className="sidebar-user" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className="avatar">{initials}</div>
            <div><strong>{user?.name || 'Admin'}</strong><small>{roleDisplay}</small></div>
          </div>
          <button
            onClick={logout}
            title="Log out"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#6b7280',
              padding: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '4px',
              transition: 'background-color 0.2s, color 0.2s'
            }}
            onMouseOver={(e) => { e.currentTarget.style.backgroundColor = '#f3f4f6'; e.currentTarget.style.color = '#374151'; }}
            onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = '#6b7280'; }}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <main className="main-workspace"><Outlet /></main>
    </div>
  );
}
