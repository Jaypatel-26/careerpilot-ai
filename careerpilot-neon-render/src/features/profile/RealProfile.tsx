import { useEffect, useState, type FormEvent } from 'react';
import { AlertCircle, Check, CheckCircle2, RefreshCw, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { profileApi, type AccountProfile, type ProfileFields } from './api';

export function initials(name: string): string {
  return name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(part => Array.from(part)[0]).join('').toUpperCase() || 'U';
}

function displayError(error: unknown): string {
  return error instanceof Error ? error.message : 'Could not complete the request. Please try again.';
}

export function RealProfile() {
  const {session, updateSessionUser} = useAuth();
  const [profile, setProfile] = useState<AccountProfile | null>(null);
  const [draft, setDraft] = useState<ProfileFields | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const userId = session?.user.id;
  useEffect(() => {
    let active = true;
    setLoading(true); setError(''); setProfile(null); setDraft(null);
    profileApi.get().then(data => {
      if (!active) return;
      setProfile(data);
      setDraft({full_name: data.full_name, target_role: data.target_role, experience_level: data.experience_level, skills: data.skills, career_goals: data.career_goals});
    }).catch(err => {if(active) setError(displayError(err));}).finally(() => {if(active) setLoading(false);});
    return () => {active = false;};
  }, [userId, attempt]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft || !session || saving) return;
    setSaving(true); setError(''); setSaved(false);
    try {
      const result = await profileApi.update(draft);
      setProfile(result);
      setDraft({full_name: result.full_name, target_role: result.target_role, experience_level: result.experience_level, skills: result.skills, career_goals: result.career_goals});
      updateSessionUser({...session.user, full_name: result.full_name});
      setSaved(true);
    } catch (err) { setError(displayError(err)); }
    finally { setSaving(false); }
  }
  const change = <K extends keyof ProfileFields>(key: K, value: ProfileFields[K]) => {
    setDraft(current => current ? {...current, [key]: value} : current); setSaved(false);
  };
  return <>
    <div className="page-head"><div><div className="eyebrow">YOUR ACCOUNT</div><h1>A little about you.</h1><p>Your goals, your journey. Make this space your own.</p></div></div>
    {loading ? <div className="card profile-form"><div className="checking" role="status"><RefreshCw size={15}/> Loading your profile…</div></div> : !profile || !draft ? <div className="card profile-form"><div className="real-error" role="alert"><AlertCircle size={16}/>{error || 'Your profile could not be loaded.'}</div><button className="btn btn-outline" onClick={() => setAttempt(x => x + 1)}>Try again</button> <Link className="text-link" to="/login">Log in</Link></div> :
    <div className="profile-layout">
      <div className="card profile-form">
        <div className="setup-title"><span className="stat-icon mint"><UserRound size={20}/></span><div><h2>Career profile</h2><p>Help shape your preparation around your goals.</p></div></div>
        <div className="demo-note"><CheckCircle2 size={14}/> Saved to your account when you click Save changes.</div>
        <form onSubmit={save}><fieldset disabled={saving} className="profile-fieldset">
          <div className="form-row"><label>Full name<input value={draft.full_name} maxLength={120} required onChange={e=>change('full_name',e.target.value)}/></label><label>Target role<input value={draft.target_role} maxLength={150} onChange={e=>change('target_role',e.target.value)} placeholder="e.g. Frontend Developer"/></label></div>
          <label>Experience level<select value={draft.experience_level} onChange={e=>change('experience_level',e.target.value as ProfileFields['experience_level'])}><option value="">Select your level</option><option>Student</option><option>Fresher</option><option>Experienced</option></select></label>
          <label>Skills <span className="label-hint">Separate skills with commas.</span><input value={draft.skills} maxLength={2000} onChange={e=>change('skills',e.target.value)} placeholder="e.g. React, JavaScript, Problem solving"/></label>
          <label>Career goals<textarea rows={4} value={draft.career_goals} maxLength={5000} onChange={e=>change('career_goals',e.target.value)} placeholder="What are you working towards?"/></label>
          {error&&<div className="real-error" role="alert"><AlertCircle size={16}/>{error}</div>}
          {saved&&<div className="notice" role="status"><CheckCircle2 size={17}/>Profile saved to your account.</div>}
          <button type="submit" disabled={saving || !draft.full_name.trim()} className="btn btn-dark">{saving?'Saving…':'Save changes'} <Check size={16}/></button>
        </fieldset></form>
      </div>
      <div className="card profile-preview"><div className="profile-avatar">{initials(profile.full_name)}</div><h3>{profile.full_name}</h3><p>{profile.email}</p><p>{profile.target_role || 'Add your target role'}</p>{profile.experience_level&&<span className="badge badge-green">{profile.experience_level}</span>}<div className="tip-divider"/><small>YOUR SKILLS</small><div className="skill-tags">{profile.skills.split(',').map(s=>s.trim()).filter(Boolean).map((skill,i)=><span key={`${skill}-${i}`} className="badge badge-neutral">{skill}</span>)}</div>{!profile.skills.trim()&&<p>Add skills to your profile.</p>}</div>
    </div>}
  </>;
}
