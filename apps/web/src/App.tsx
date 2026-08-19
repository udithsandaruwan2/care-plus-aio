import { lazy, Suspense, type ComponentType } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { RequireAuth } from './auth/RequireAuth';
import { RequireOtp } from './auth/RequireOtp';
import { AppShell } from './components/layout/AppShell';
import { PublicSiteLayout } from './components/layout/PublicSiteLayout';

function lazyNamed<T extends Record<string, ComponentType>>(
  loader: () => Promise<T>,
  exportName: keyof T & string,
) {
  return lazy(() => loader().then((mod) => ({ default: mod[exportName] as ComponentType })));
}

const PublicHomePage = lazyNamed(() => import('./pages/PublicHomePage'), 'PublicHomePage');
const LoginPage = lazyNamed(() => import('./pages/LoginPage'), 'LoginPage');
const RegisterPage = lazyNamed(() => import('./pages/RegisterPage'), 'RegisterPage');
const ContactPage = lazyNamed(() => import('./pages/ContactPage'), 'ContactPage');
const PrivacyNoticePage = lazyNamed(() => import('./pages/PrivacyNoticePage'), 'PrivacyNoticePage');
const CatalogPage = lazyNamed(() => import('./pages/CatalogPage'), 'CatalogPage');
const BrowseCaregiversPage = lazyNamed(
  () => import('./pages/BrowseCaregiversPage'),
  'BrowseCaregiversPage',
);
const CaregiverDetailPage = lazyNamed(
  () => import('./pages/CaregiverDetailPage'),
  'CaregiverDetailPage',
);
const PlatformHubPage = lazyNamed(() => import('./pages/PlatformHubPage'), 'PlatformHubPage');
const HomePage = lazyNamed(() => import('./pages/HomePage'), 'HomePage');
const PatientOnboardingPage = lazyNamed(
  () => import('./pages/PatientOnboardingPage'),
  'PatientOnboardingPage',
);
const CaregiverOnboardingPage = lazyNamed(
  () => import('./pages/CaregiverOnboardingPage'),
  'CaregiverOnboardingPage',
);
const CareRequestsPage = lazyNamed(() => import('./pages/CareRequestsPage'), 'CareRequestsPage');
const MessagesPage = lazyNamed(() => import('./pages/MessagesPage'), 'MessagesPage');
const AccountPage = lazyNamed(() => import('./pages/AccountPage'), 'AccountPage');
const OtpPage = lazyNamed(() => import('./pages/OtpPage'), 'OtpPage');
const NotificationPreferencesPage = lazyNamed(
  () => import('./pages/NotificationPreferencesPage'),
  'NotificationPreferencesPage',
);
const PrivacySettingsPage = lazyNamed(
  () => import('./pages/PrivacySettingsPage'),
  'PrivacySettingsPage',
);
const MedicalRecordsPage = lazyNamed(
  () => import('./pages/MedicalRecordsPage'),
  'MedicalRecordsPage',
);
const CheckoutPage = lazyNamed(() => import('./pages/CheckoutPage'), 'CheckoutPage');
const OrderPayPage = lazyNamed(() => import('./pages/OrderPayPage'), 'OrderPayPage');
const OrderSuccessPage = lazyNamed(() => import('./pages/OrderSuccessPage'), 'OrderSuccessPage');
const OrderFailedPage = lazyNamed(() => import('./pages/OrderFailedPage'), 'OrderFailedPage');
const CaregiverPresencePage = lazyNamed(
  () => import('./pages/CaregiverPresencePage'),
  'CaregiverPresencePage',
);
const SchedulePage = lazyNamed(() => import('./pages/SchedulePage'), 'SchedulePage');
const AdminUsersPage = lazyNamed(() => import('./pages/AdminUsersPage'), 'AdminUsersPage');
const AdminCatalogPage = lazyNamed(() => import('./pages/AdminCatalogPage'), 'AdminCatalogPage');
const AdminAnalyticsPage = lazyNamed(
  () => import('./pages/AdminAnalyticsPage'),
  'AdminAnalyticsPage',
);
const AdminAuditPage = lazyNamed(() => import('./pages/AdminAuditPage'), 'AdminAuditPage');
const LeadsPage = lazyNamed(() => import('./pages/LeadsPage'), 'LeadsPage');

function RouteFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center px-6">
      <p className="text-sm text-muted">Loading…</p>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route element={<PublicSiteLayout />}>
            <Route path="/" element={<PublicHomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/privacy" element={<PrivacyNoticePage />} />
            <Route path="/catalog" element={<CatalogPage />} />
            <Route path="/caregivers" element={<BrowseCaregiversPage />} />
            <Route path="/caregivers/:id" element={<CaregiverDetailPage />} />
          </Route>

          <Route element={<RequireAuth />}>
            <Route element={<AppShell />}>
              <Route path="/hub" element={<PlatformHubPage />} />
              <Route path="/platform" element={<Navigate to="/hub" replace />} />
              <Route path="/app" element={<HomePage />} />
              <Route path="/onboarding" element={<PatientOnboardingPage />} />
              <Route path="/caregiver-onboarding" element={<CaregiverOnboardingPage />} />
              <Route path="/requests" element={<CareRequestsPage />} />
              <Route path="/messages" element={<MessagesPage />} />
              <Route path="/account" element={<AccountPage />} />
              <Route path="/otp" element={<OtpPage />} />
              <Route path="/settings/notifications" element={<NotificationPreferencesPage />} />
              <Route path="/settings/privacy" element={<PrivacySettingsPage />} />
              <Route element={<RequireOtp />}>
                <Route path="/records" element={<MedicalRecordsPage />} />
                <Route path="/requests/:careRequestId/checkout" element={<CheckoutPage />} />
                <Route path="/orders/:orderId/pay" element={<OrderPayPage />} />
              </Route>
              <Route path="/orders/:orderId/success" element={<OrderSuccessPage />} />
              <Route path="/orders/:orderId/failed" element={<OrderFailedPage />} />
              <Route path="/presence" element={<CaregiverPresencePage />} />
              <Route path="/schedule" element={<SchedulePage />} />
              <Route path="/users" element={<AdminUsersPage />} />
              <Route path="/admin/catalog" element={<AdminCatalogPage />} />
              <Route path="/admin/analytics" element={<AdminAnalyticsPage />} />
              <Route path="/admin/audit" element={<AdminAuditPage />} />
              <Route path="/leads" element={<LeadsPage />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AuthProvider>
  );
}
