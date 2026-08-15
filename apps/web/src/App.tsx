import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { RequireAuth } from './auth/RequireAuth';
import { RequireOtp } from './auth/RequireOtp';
import { AppShell } from './components/layout/AppShell';
import { PublicSiteLayout } from './components/layout/PublicSiteLayout';
import { BrowseCaregiversPage } from './pages/BrowseCaregiversPage';
import { CaregiverDetailPage } from './pages/CaregiverDetailPage';
import { CaregiverOnboardingPage } from './pages/CaregiverOnboardingPage';
import { CaregiverPresencePage } from './pages/CaregiverPresencePage';
import { CareRequestsPage } from './pages/CareRequestsPage';
import { CheckoutPage } from './pages/CheckoutPage';
import { ContactPage } from './pages/ContactPage';
import { CatalogPage } from './pages/CatalogPage';
import { HomePage } from './pages/HomePage';
import { PublicHomePage } from './pages/PublicHomePage';
import { LeadsPage } from './pages/LeadsPage';
import { LoginPage } from './pages/LoginPage';
import { OrderFailedPage } from './pages/OrderFailedPage';
import { OrderPayPage } from './pages/OrderPayPage';
import { OrderSuccessPage } from './pages/OrderSuccessPage';
import { MessagesPage } from './pages/MessagesPage';
import { MedicalRecordsPage } from './pages/MedicalRecordsPage';
import { NotificationPreferencesPage } from './pages/NotificationPreferencesPage';
import { OtpPage } from './pages/OtpPage';
import { AccountPage } from './pages/AccountPage';
import { PrivacyNoticePage } from './pages/PrivacyNoticePage';
import { PrivacySettingsPage } from './pages/PrivacySettingsPage';
import { AdminAnalyticsPage } from './pages/AdminAnalyticsPage';
import { AdminAuditPage } from './pages/AdminAuditPage';
import { AdminCatalogPage } from './pages/AdminCatalogPage';
import { AdminUsersPage } from './pages/AdminUsersPage';
import { PatientOnboardingPage } from './pages/PatientOnboardingPage';
import { PlatformHubPage } from './pages/PlatformHubPage';
import { RegisterPage } from './pages/RegisterPage';
import { SchedulePage } from './pages/SchedulePage';

export function App() {
  return (
    <AuthProvider>
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
            <Route path="/platform" element={<PlatformHubPage />} />
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
    </AuthProvider>
  );
}
