import { apiRequest } from '../../lib/apiClient';
export type User = { id: string; email: string; full_name: string; created_at: string };
export type AuthResponse = { access_token: string; token_type: 'bearer'; expires_in: number; user: User };
export const authApi = {
  signup: (full_name: string, email: string, password: string) => apiRequest<AuthResponse>('/auth/signup', {method:'POST',body:JSON.stringify({full_name,email,password})}, false),
  login: (email: string, password: string) => apiRequest<AuthResponse>('/auth/login', {method:'POST',body:JSON.stringify({email,password})}, false),
  me: () => apiRequest<User>('/auth/me'),
  logout: () => apiRequest<void>('/auth/logout', {method:'POST'}),
};
