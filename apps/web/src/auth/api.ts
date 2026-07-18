import { createApiClient } from '@care-plus/api-client';
import { getAccessToken } from './session';

export const api = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  getAccessToken,
});
