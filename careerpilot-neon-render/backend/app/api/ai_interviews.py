"""Account-owned AI interview operations, serialized per interview on PostgreSQL."""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.core.config import get_settings
from app.core.security import current_user
from app.db.session import get_db
from app.models import InterviewSession, InterviewQuestion, InterviewAnswer, AnswerEvaluation, InterviewReport
from app.schemas.ai_interview import AnswerSubmit
from app.services import gemini

router = APIRouter(prefix='/interviews', tags=['AI text interviews'])
_limit_lock = Lock()
_calls: dict[str, deque[float]] = defaultdict(deque)


def limit_ai(user_id: UUID):
    now = monotonic()
    with _limit_lock:
        for key in list(_calls):
            if not _calls[key] or _calls[key][-1] <= now - 3600:
                del _calls[key]
        key = str(user_id)
        if key not in _calls and len(_calls) >= 10000:
            raise HTTPException(429, 'Too many AI requests. Please try later.', headers={'Retry-After':'60'})
        q = _calls[key]
        while q and q[0] <= now - 3600:
            q.popleft()
        if len(q) >= 30:
            raise HTTPException(429, 'AI request limit reached. Please try again later.', headers={'Retry-After':'3600'})
        q.append(now)


def get_owned(db: Session, session_id: UUID, user_id: UUID, lock: bool = False) -> InterviewSession:
    stmt = select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == user_id)
    if lock:
        # On PostgreSQL, held through provider call and DB commit. Serializes starts,
        # submissions, evaluation and completion across workers for this session.
        stmt = stmt.with_for_update()
    result = db.scalar(stmt)
    if result is None:
        raise HTTPException(404, 'Interview not found.')
    return result


def all_questions(db: Session, interview: InterviewSession):
    return list(db.scalars(select(InterviewQuestion).where(InterviewQuestion.session_id == interview.id)
                           .options(selectinload(InterviewQuestion.answer).selectinload(InterviewAnswer.evaluation))
                           .order_by(InterviewQuestion.position)))


def current_question(questions):
    return next((q for q in questions if q.answer is None or (q.answer.status == 'submitted' and q.answer.evaluation is None)), None)


def current_data(db: Session, interview: InterviewSession):
    questions = all_questions(db, interview)
    q = current_question(questions)
    return {'id':str(interview.id), 'status':interview.status, 'target_role':interview.target_role,
            'total':len(questions), 'answered':sum(x.answer is not None and x.answer.status == 'submitted' for x in questions),
            'skipped':sum(x.answer is not None and x.answer.status == 'skipped' for x in questions),
            'ready_to_complete':bool(questions) and q is None,
            'current': None if q is None else {'id':str(q.id), 'position':q.position, 'question':q.question_text,
                         'category':q.category, 'answer':q.answer.transcript if q.answer else None,
                         'answer_saved': bool(q.answer), 'evaluation':q.answer.evaluation.feedback if q.answer and q.answer.evaluation else None}}


def provider_call(user_id, fn, *args):
    limit_ai(user_id)
    try:
        return fn(*args)
    except gemini.AIServiceError as exc:
        raise HTTPException(exc.status_code, exc.message, headers={'Retry-After':str(exc.retry_after)} if exc.retry_after else None) from exc


@router.post('/{session_id}/start')
def start(session_id: UUID, user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    interview = get_owned(db, session_id, user_id, lock=True)
    existing = all_questions(db, interview)
    if existing:
        return current_data(db, interview)
    if interview.status != 'draft':
        raise HTTPException(409, 'This interview cannot be started.')
    if interview.question_count > 5:
        raise HTTPException(422, 'AI interviews support at most 5 questions. Create a new draft with 5 or fewer.')
    generated = provider_call(user_id, gemini.questions, interview.target_role, interview.question_focus or interview.interview_type,
                              interview.difficulty, interview.question_count, interview.experience_level or 'Fresher', interview.skills or '')
    for position, q in enumerate(generated.questions, 1):
        db.add(InterviewQuestion(session_id=interview.id, position=position, question_text=q.question, category=q.category))
    interview.status = 'in_progress'
    db.commit()
    return current_data(db, interview)


@router.get('/{session_id}/current')
def current(session_id: UUID, user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    return current_data(db, get_owned(db, session_id, user_id))


def require_question(db, interview, question_id):
    questions = all_questions(db, interview)
    target = next((q for q in questions if q.id == question_id), None)
    if target is None:
        raise HTTPException(404, 'Question not found.')
    return target, questions


@router.post('/{session_id}/questions/{question_id}/answer')
def submit(session_id: UUID, question_id: UUID, payload: AnswerSubmit, user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    interview = get_owned(db, session_id, user_id, lock=True)
    q, questions = require_question(db, interview, question_id)
    if q.answer:
        if q.answer.status == 'submitted' and q.answer.transcript == payload.answer:
            return {'saved': True, 'evaluated': bool(q.answer.evaluation)}
        raise HTTPException(409, 'An answer or skip is already saved for this question.')
    if interview.status != 'in_progress' or current_question(questions) != q:
        raise HTTPException(409, 'Answer the current question first.')
    db.add(InterviewAnswer(question_id=q.id, transcript=payload.answer, input_mode='text', status='submitted'))
    db.commit()
    return {'saved': True, 'evaluated': False}


@router.post('/{session_id}/questions/{question_id}/evaluate')
def evaluate(session_id: UUID, question_id: UUID, user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    interview = get_owned(db, session_id, user_id, lock=True)
    q, questions = require_question(db, interview, question_id)
    if q.answer and q.answer.evaluation:
        return q.answer.evaluation.feedback
    if interview.status != 'in_progress' or current_question(questions) != q or not q.answer or q.answer.status != 'submitted':
        raise HTTPException(409, 'Submit an answer to the current question first.')
    result = provider_call(user_id, gemini.evaluate, interview.target_role, q.question_text, q.answer.transcript)
    feedback = result.model_dump()
    db.add(AnswerEvaluation(answer_id=q.answer.id, score=result.score, feedback=feedback,
                            model_name=get_settings().gemini_model, prompt_version='text-v1'))
    db.commit()
    return feedback


@router.post('/{session_id}/questions/{question_id}/skip')
def skip(session_id: UUID, question_id: UUID, user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    interview = get_owned(db, session_id, user_id, lock=True)
    q, questions = require_question(db, interview, question_id)
    if q.answer:
        if q.answer.status == 'skipped':
            return {'skipped':True}
        raise HTTPException(409, 'This question already has an answer.')
    if interview.status != 'in_progress' or current_question(questions) != q:
        raise HTTPException(409, 'Skip the current question first.')
    db.add(InterviewAnswer(question_id=q.id, input_mode='text', status='skipped'))
    db.commit()
    return {'skipped':True}


@router.post('/{session_id}/complete')
def complete(session_id: UUID, user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    interview = get_owned(db, session_id, user_id, lock=True)
    saved = db.scalar(select(InterviewReport).where(InterviewReport.session_id == interview.id))
    if saved and saved.details:
        return saved.details
    if saved:
        raise HTTPException(409, 'A legacy report already exists for this interview.')
    questions = all_questions(db, interview)
    if interview.status != 'in_progress' or not questions or current_question(questions) is not None:
        raise HTTPException(409, 'Answer or skip every question and finish pending evaluations first.')
    evaluated = [q for q in questions if q.answer and q.answer.evaluation]
    answered, skipped = len(evaluated), len(questions) - len(evaluated)
    # Skips count as zero in the overall average, to avoid inflated scores.
    average = round(sum(q.answer.evaluation.score or 0 for q in evaluated) / len(questions), 2)
    if evaluated:
        evidence = [{'question':q.question_text, 'score':q.answer.evaluation.score,
                     'strengths':(q.answer.evaluation.feedback or {}).get('strengths',[]),
                     'weaknesses':(q.answer.evaluation.feedback or {}).get('weaknesses',[]),
                     'missing_concepts':(q.answer.evaluation.feedback or {}).get('missing_concepts',[])} for q in evaluated]
        narrative = provider_call(user_id, gemini.report, interview.target_role, interview.question_focus or interview.interview_type, evidence).model_dump()
        model = get_settings().gemini_model
    else:
        # No evidence: do not spend quota or invent an assessment.
        narrative = {'strong_areas':[], 'weak_areas':[], 'technical_analysis':'No answers were submitted.',
                     'communication_feedback':'No answers were submitted.', 'recommendations':['Try answering questions in a new interview.'], 'practice_roadmap':[]}
        model = None
    result = {'overall_score':average, 'total_questions':len(questions), 'answered_questions':answered, 'skipped_questions':skipped, **narrative}
    db.add(InterviewReport(session_id=interview.id, overall_score=round(average*10), details=result, model_name=model, prompt_version='text-v1'))
    interview.status = 'completed'
    db.commit()
    return result


@router.get('/{session_id}/report')
def get_report(session_id: UUID, user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    interview = get_owned(db, session_id, user_id)
    report = db.scalar(select(InterviewReport).where(InterviewReport.session_id == interview.id))
    if not report or not report.details:
        raise HTTPException(404, 'Report not found.')
    return report.details
