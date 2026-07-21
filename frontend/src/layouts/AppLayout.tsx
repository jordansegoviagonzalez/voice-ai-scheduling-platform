import {
  Activity,
  CalendarDays,
  ClipboardList,
  LayoutDashboard,
  Route,
  Stethoscope,
} from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';

const navigation = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/calls', label: 'Calls', icon: ClipboardList },
  { to: '/appointments', label: 'Appointments', icon: CalendarDays },
  { to: '/physicians', label: 'Physicians', icon: Stethoscope },
  { to: '/routing-audit', label: 'Routing Audit', icon: Route },
  { to: '/simulator', label: 'Call Simulator', icon: Activity },
];

export function AppLayout() {
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
        <div className="sidebar-user">
          <div className="avatar">JW</div>
          <div><strong>Dr. James Walsh</strong><small>Administrator</small></div>
        </div>
      </aside>
      <main className="main-workspace"><Outlet /></main>
    </div>
  );
}
