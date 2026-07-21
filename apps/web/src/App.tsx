import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { RequireAuth } from './auth/RequireAuth';
import { BrowseCaregiversPage } from './pages/BrowseCaregiversPage';
import { CaregiverDetailPage } from './pages/CaregiverDetailPage';
import { CaregiverOnboardingPage } from './pages/CaregiverOnboardingPage';
import { CaregiverPresencePage } from './pages/CaregiverPresencePage';
import { CareRequestsPage } from './pages/CareRequestsPage';
import { CheckoutPage } from './pages/CheckoutPage';
import { ContactPage } from './pages/ContactPage';
import { CatalogPage } from './pages/CatalogPage';
import { HomePage } from './pages/HomePage';
import { LeadsPage } from './pages/LeadsPage';
import { LoginPage } from './pages/LoginPage';
import { OrderFailedPage } from './pages/OrderFailedPage';
import { OrderPayPage } from './pages/OrderPayPage';
import { OrderSuccessPage } from './pages/OrderSuccessPage';
import { PatientOnboardingPage } from './pages/PatientOnboardingPage';
import { RegisterPage } from './pages/RegisterPage';

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/caregivers" element={<BrowseCaregiversPage />} />
          <Route path="/caregivers/:id" element={<CaregiverDetailPage />} />
          <Route path="/onboarding" element={<PatientOnboardingPage />} />
          <Route path="/caregiver-onboarding" element={<CaregiverOnboardingPage />} />
          <Route path="/requests" element={<CareRequestsPage />} />
          <Route path="/requests/:careRequestId/checkout" element={<CheckoutPage />} />
          <Route path="/orders/:orderId/pay" element={<OrderPayPage />} />
          <Route path="/orders/:orderId/success" element={<OrderSuccessPage />} />
          <Route path="/orders/:orderId/failed" element={<OrderFailedPage />} />
          <Route path="/presence" element={<CaregiverPresencePage />} />
          <Route path="/leads" element={<LeadsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
