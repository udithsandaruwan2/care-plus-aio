import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import { RequireAuth } from './auth/RequireAuth';
import { BrowseCaregiversPage } from './pages/BrowseCaregiversPage';
import { CaregiverDetailPage } from './pages/CaregiverDetailPage';
import { CaregiverOnboardingPage } from './pages/CaregiverOnboardingPage';
import { CaregiverPresencePage } from './pages/CaregiverPresencePage';
import { CareRequestsPage } from './pages/CareRequestsPage';
import { ContactPage } from './pages/ContactPage';
import { HomePage } from './pages/HomePage';
import { LeadsPage } from './pages/LeadsPage';
import { LoginPage } from './pages/LoginPage';
import { PatientOnboardingPage } from './pages/PatientOnboardingPage';
import { RegisterPage } from './pages/RegisterPage';

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/contact" element={<ContactPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/caregivers" element={<BrowseCaregiversPage />} />
          <Route path="/caregivers/:id" element={<CaregiverDetailPage />} />
          <Route path="/onboarding" element={<PatientOnboardingPage />} />
          <Route path="/caregiver-onboarding" element={<CaregiverOnboardingPage />} />
          <Route path="/requests" element={<CareRequestsPage />} />
          <Route path="/presence" element={<CaregiverPresencePage />} />
          <Route path="/leads" element={<LeadsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
