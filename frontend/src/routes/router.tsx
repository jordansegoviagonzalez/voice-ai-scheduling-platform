import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { AppointmentsPage } from '../pages/AppointmentsPage';
import { CallDetailPage } from '../pages/CallDetailPage';
import { CallsPage } from '../pages/CallsPage';
import { OverviewPage } from '../pages/OverviewPage';
import { PhysiciansPage } from '../pages/PhysiciansPage';
import { RoutingAuditPage } from '../pages/RoutingAuditPage';
import { SimulatorPage } from '../pages/SimulatorPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'calls', element: <CallsPage /> },
      { path: 'calls/:callId', element: <CallDetailPage /> },
      { path: 'appointments', element: <AppointmentsPage /> },
      { path: 'physicians', element: <PhysiciansPage /> },
      { path: 'routing-audit', element: <RoutingAuditPage /> },
      { path: 'simulator', element: <SimulatorPage /> },
    ],
  },
]);
