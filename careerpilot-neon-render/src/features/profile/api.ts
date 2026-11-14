import { apiRequest } from '../../lib/apiClient';
export type ProfileFields = {
  full_name: string;
  target_role: string;
  experience_level: '' | 'Student' | 'Fresher' | 'Experienced';
  skills: string;
  career_goals: string;
};
export type AccountProfile = ProfileFields & { id: string; email: string };
export const profileApi = {
  get: () => apiRequest<AccountProfile>('/profile'),
  update: (body: ProfileFields) => apiRequest<AccountProfile>('/profile', { method: 'PATCH', body: JSON.stringify(body) }),
};
