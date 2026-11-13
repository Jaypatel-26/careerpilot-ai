import { apiRequest } from '../../lib/apiClient';
export type InterviewType = 'technical' | 'behavioral' | 'mixed';
export type Difficulty = 'beginner' | 'intermediate' | 'advanced';
export type InterviewCreate = { target_role: string; interview_type: InterviewType; difficulty: Difficulty; question_count: number };
export type InterviewSession = InterviewCreate & { id: string; status: 'draft' | 'in_progress' | 'completed' | 'abandoned' | 'failed'; created_at: string; updated_at: string };
export const interviewApi = {
  create: (body: InterviewCreate) => apiRequest<InterviewSession>('/interviews', { method: 'POST', body: JSON.stringify(body) }),
  list: () => apiRequest<InterviewSession[]>('/interviews?limit=50'),
  get: (id: string) => apiRequest<InterviewSession>(`/interviews/${encodeURIComponent(id)}`),
  remove: (id: string) => apiRequest<void>(`/interviews/${encodeURIComponent(id)}`, { method: 'DELETE' }),
};
