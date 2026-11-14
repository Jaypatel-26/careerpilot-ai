import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { ApiError, getAccessToken, setAccessToken } from '../../lib/apiClient';
import { authApi, type AuthResponse, type User } from './api';

type AuthSession = { access_token: string; user: User };
type AuthState = {
  session: AuthSession | null; loading: boolean; error: string;
  signIn: (email:string,password:string)=>Promise<void>;
  signUp: (name:string,email:string,password:string)=>Promise<void>;
  signOut: ()=>Promise<void>;
  updateSessionUser: (user: User)=>void;
};
const AuthContext = createContext<AuthState | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(Boolean(getAccessToken()));
  const [error, setError] = useState('');
  useEffect(() => {
    const expire = () => { setSession(null); setError('Your session has expired. Please log in again.'); };
    window.addEventListener('careerpilot:session-expired', expire);
    return () => window.removeEventListener('careerpilot:session-expired', expire);
  }, []);
  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    let active = true;
    authApi.me().then(user => { if (active && getAccessToken() === token) setSession({access_token:token,user}); })
      .catch(err => { if (!active) return; if (err instanceof ApiError && err.status === 401) { setAccessToken(null); setError('Your session has expired. Please log in again.'); } else { setError('Could not verify your session. Please refresh when the backend is available.'); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  function accept(result: AuthResponse) { setAccessToken(result.access_token); setSession({access_token:result.access_token,user:result.user});setError(''); }
  async function signIn(email:string,password:string) { accept(await authApi.login(email,password)); }
  async function signUp(name:string,email:string,password:string) { accept(await authApi.signup(name,email,password)); }
  async function signOut() {
    try { await authApi.logout(); }
    catch (err) { if (!(err instanceof ApiError && err.status === 401)) throw err; }
    setAccessToken(null);setSession(null);setError('');
  }
  function updateSessionUser(user: User) { setSession(current => current && current.user.id === user.id ? {...current, user} : current); }
  return <AuthContext.Provider value={{session,loading,error,signIn,signUp,signOut,updateSessionUser}}>{children}</AuthContext.Provider>;
}
export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth requires AuthProvider');
  return context;
}
