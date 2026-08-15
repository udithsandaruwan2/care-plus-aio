import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { userNeedsOtp } from '@care-plus/api-client';
import { useAuth } from './AuthContext';

/** Hire / pay / records routes when email OTP is enabled. */
export function RequireOtp() {
  const { user } = useAuth();
  const location = useLocation();
  if (userNeedsOtp(user)) {
    return <Navigate to="/otp" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
