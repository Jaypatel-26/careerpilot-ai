import { useEffect, useRef, useState } from 'react';
import { AlertCircle, Mic, Square, Volume2 } from 'lucide-react';

type RecognitionResult = { isFinal: boolean; 0: { transcript: string } };
type RecognitionEvent = { results: { length: number; [index: number]: RecognitionResult } };
type RecognitionError = { error: string };
type Recognition = {
  continuous: boolean; interimResults: boolean; lang: string;
  onstart: (() => void) | null; onend: (() => void) | null;
  onerror: ((event: RecognitionError) => void) | null;
  onresult: ((event: RecognitionEvent) => void) | null;
  start: () => void; stop: () => void; abort: () => void;
};
type SpeechWindow = Window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
type Props = {question: string; answer: string; disabled: boolean; onTranscript: (value: string) => void; onListeningChange: (active: boolean) => void};

export function VoiceControls({question, answer, disabled, onTranscript, onListeningChange}: Props) {
  const win = window as SpeechWindow;
  const RecognitionConstructor = win.SpeechRecognition || win.webkitSpeechRecognition;
  const canSpeak = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
  const [state,setState] = useState<'idle'|'starting'|'listening'|'stopping'>('idle');
  const [message,setMessage] = useState('');
  const [speechMessage,setSpeechMessage] = useState('');
  const recognition = useRef<Recognition|null>(null);
  const alive = useRef(true);
  const onListening = useRef(onListeningChange); onListening.current = onListeningChange;

  function readQuestion() {
    if (!canSpeak) {setSpeechMessage('Question audio is not supported in this browser; please read the question.');return;}
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(question);
      utterance.lang = 'en-US';
      utterance.onerror = event => {if(alive.current && event.error !== 'interrupted' && event.error !== 'canceled')setSpeechMessage('Could not play the question. Please try Repeat question or read the text.');};
      utterance.onstart = () => {if(alive.current)setSpeechMessage('');};
      window.speechSynthesis.speak(utterance);
    } catch { setSpeechMessage('Could not play the question. Please read the text.'); }
  }
  useEffect(() => {
    alive.current = true;
    // Browsers may block automatic audio until the user interacts. Replay is always available.
    readQuestion();
    return () => {
      alive.current = false;
      const old = recognition.current;
      recognition.current = null;
      if (old) {old.onstart=null;old.onresult=null;old.onerror=null;old.onend=null;try{old.abort()}catch{/* already stopped */}}
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
      onListening.current(false);
    };
    // Component is keyed by question; speak once on question change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question]);

  function startListening() {
    if (!RecognitionConstructor || disabled || state !== 'idle') return;
    setMessage(''); setSpeechMessage('');
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    const base = answer.trim();
    let recognizer: Recognition;
    try {
      recognizer = new RecognitionConstructor();
      recognition.current = recognizer;
      recognizer.lang = 'en-US';
      recognizer.continuous = true;
      recognizer.interimResults = true;
      recognizer.onstart = () => {if(alive.current)setState('listening');};
      recognizer.onresult = (event) => {
        if (!alive.current) return;
        const pieces: string[] = [];
        for (let i=0;i<event.results.length;i++) {
          const text=event.results[i]?.[0]?.transcript?.trim();
          if (text) pieces.push(text);
        }
        if (pieces.length) onTranscript([base,...pieces].filter(Boolean).join(' ').slice(0,5000));
      };
      recognizer.onerror = (event) => {
        if (!alive.current) return;
        const messages: Record<string,string> = {
          'not-allowed':'Microphone permission was denied. Allow microphone access in browser settings, then try again or type your answer.',
          'service-not-allowed':'Speech recognition permission was denied. Check browser settings or type your answer.',
          'audio-capture':'Microphone not found or unavailable. Check your device or type your answer.',
          'network':'Speech recognition needs a network connection. Try again or type your answer.',
          'no-speech':'No speech was detected. Try again or type your answer.',
          'aborted':'Recording was stopped.',
        };
        setMessage(messages[event.error] || 'Speech recognition stopped. Try again or type your answer.');
      };
      recognizer.onend = () => {recognition.current=null;if(alive.current){setState('idle');onListening.current(false);}};
      setState('starting');onListening.current(true);
      recognizer.start();
    } catch {
      recognition.current=null;setState('idle');onListening.current(false);
      setMessage('Could not start the microphone. Check browser permissions or type your answer.');
    }
  }
  function stopListening() {
    if (!recognition.current) return;
    setState('stopping');
    try {recognition.current.stop();} catch {recognition.current=null;setState('idle');onListening.current(false);setMessage('Recording stopped. You can edit your transcript.');}
  }
  const active = state !== 'idle';
  return <div className="voice-controls">
    <div className="voice-actions">
      <button type="button" className="btn btn-outline" onClick={readQuestion} disabled={active || !canSpeak}><Volume2 size={16}/> Repeat question</button>
      {active ? <button type="button" className="btn btn-outline" onClick={stopListening} disabled={state==='stopping'}><Square size={15}/>{state==='stopping'?'Stopping…':'Stop recording'}</button> : <button type="button" className="btn btn-outline" onClick={startListening} disabled={disabled || !RecognitionConstructor}><Mic size={16}/> Speak answer</button>}
    </div>
    {active&&<p role="status" className="voice-status">{state==='starting'?'Starting microphone…':state==='stopping'?'Finishing transcript…':'Listening… Stop recording before editing or submitting.'}</p>}
    {!RecognitionConstructor&&<p className="voice-status">Speech recognition is not supported in this browser. Try desktop Chrome, or type your answer below.</p>}
    {!canSpeak&&<p className="voice-status">Question audio is not supported in this browser. Read the question above.</p>}
    {message&&<div className="real-error" role="alert"><AlertCircle size={16}/>{message}</div>}
    {speechMessage&&<p className="voice-status">{speechMessage}</p>}
    <p className="voice-privacy">Microphone use is optional. Your browser may send audio to its speech-recognition provider for transcription. CareerPilot saves the submitted transcript, not raw audio; the transcript is sent to Gemini for feedback.</p>
  </div>;
}
