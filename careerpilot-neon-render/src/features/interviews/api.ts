import { apiRequest } from '../../lib/apiClient';
export type InterviewType = 'technical' | 'behavioral' | 'mixed';
export type QuestionFocus = InterviewType | 'hr' | 'situational';
export type Difficulty = 'beginner' | 'intermediate' | 'advanced';
export type InterviewCreate = { mode?: 'text' | 'voice'; target_role: string; interview_type: InterviewType; difficulty: Difficulty; question_count: number; question_focus?: QuestionFocus; experience_level?: 'Student' | 'Fresher' | 'Experienced'; skills?: string };
export type InterviewSession = InterviewCreate & { mode: 'text' | 'voice'; id: string; status: 'draft' | 'in_progress' | 'completed' | 'abandoned' | 'failed'; created_at: string; updated_at: string };
export type Evaluation = {score:number;strengths:string[];weaknesses:string[];missing_concepts:string[];improvement_suggestions:string[];ideal_answer:string;encouraging_feedback:string};
export type AIState = {id:string;status:InterviewSession['status'];mode:'text'|'voice';target_role:string;total:number;answered:number;skipped:number;ready_to_complete:boolean;current:null|{id:string;position:number;question:string;category:string;answer:string|null;answer_saved:boolean;evaluation:Evaluation|null}};
export type AIReport = {overall_score:number;total_questions:number;answered_questions:number;skipped_questions:number;strong_areas:string[];weak_areas:string[];technical_analysis:string;communication_feedback:string;recommendations:string[];practice_roadmap:string[]};
const root=(id:string)=>`/interviews/${encodeURIComponent(id)}`;
const qroot=(id:string,q:string)=>`${root(id)}/questions/${encodeURIComponent(q)}`;
export const interviewApi = {
  create: (body: InterviewCreate) => apiRequest<InterviewSession>('/interviews', { method: 'POST', body: JSON.stringify(body) }),
  list: () => apiRequest<InterviewSession[]>('/interviews?limit=50'),
  get: (id: string) => apiRequest<InterviewSession>(root(id)),
  remove: (id: string) => apiRequest<void>(root(id), { method: 'DELETE' }),
  start: (id:string) => apiRequest<AIState>(`${root(id)}/start`, {method:'POST'}),
  current: (id:string) => apiRequest<AIState>(`${root(id)}/current`),
  answer: (id:string,q:string,answer:string,input_mode:'text'|'voice'='text') => apiRequest<{saved:boolean}>(`${qroot(id,q)}/answer`, {method:'POST',body:JSON.stringify({answer,input_mode})}),
  evaluate: (id:string,q:string) => apiRequest<Evaluation>(`${qroot(id,q)}/evaluate`, {method:'POST'}),
  skip: (id:string,q:string) => apiRequest<{skipped:boolean}>(`${qroot(id,q)}/skip`, {method:'POST'}),
  end: (id:string) => apiRequest<{status:string}>(`${root(id)}/end`, {method:'POST'}),
  complete: (id:string) => apiRequest<AIReport>(`${root(id)}/complete`, {method:'POST'}),
  report: (id:string) => apiRequest<AIReport>(`${root(id)}/report`),
};
