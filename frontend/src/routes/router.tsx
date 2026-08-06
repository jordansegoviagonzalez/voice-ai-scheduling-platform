import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { AppointmentsPage } from '../pages/AppointmentsPage';
import { CallDetailPage } from '../pages/CallDetailPage';
import { CallsPage } from '../pages/CallsPage';
import { OverviewPage } from '../pages/OverviewPage';
import { OrganizationsPage } from '../pages/OrganizationsPage';
import { PhysiciansPage } from '../pages/PhysiciansPage';
import { RoutingAuditPage } from '../pages/RoutingAuditPage';
import { SimulatorPage } from '../pages/SimulatorPage';
import { ChatPage } from '../pages/ChatPage';
import { WebChatSessionsPage } from '../pages/WebChatSessionsPage';
import { PatientsPage } from '../pages/PatientsPage';
import { SignInPage } from '../pages/SignInPage';
import { PatientProfilePage } from '../pages/PatientProfilePage';
import { ProtectedAdminRoute } from '../components/ProtectedAdminRoute';
import { Navigate } from 'react-router-dom';

export const router = createBrowserRouter([
  {
    path: '/admin/login',
    element: <Navigate to="/sign-in?role=admin" replace />,
  },
  {
    path: '/sign-in',
    element: <SignInPage />,
  },
  {
    path: '/chat',
    element: <ChatPage />,
  },
  {
    path: '/schedule',
    element: <ChatPage />,
  },
  {
    path: '/patient/profile',
    element: <PatientProfilePage />,
  },
  {
    path: '/',
    element: <ProtectedAdminRoute />,
    children: [
      {
        path: '/',
        element: <AppLayout />,
        children: [
          { index: true, element: <OverviewPage /> },
          { path: 'organizations', element: <OrganizationsPage /> },
          { path: 'calls', element: <CallsPage /> },
          { path: 'calls/:callId', element: <CallDetailPage /> },
          { path: 'appointments', element: <AppointmentsPage /> },
          { path: 'physicians', element: <PhysiciansPage /> },
          { path: 'routing-audit', element: <RoutingAuditPage /> },
          { path: 'simulator', element: <SimulatorPage /> },
          { path: 'web-chat-sessions', element: <WebChatSessionsPage /> },
          { path: 'web-chat-sessions/:sessionId', element: <WebChatSessionsPage /> },
          { path: 'patients', element: <PatientsPage /> },
        ],
      },
    ],
  },
]);
