"""Bounded subprocess invocation; never persist uploaded files in application storage."""
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import BoundedSemaphore
from fastapi import HTTPException

MAX_BYTES=5*1024*1024
_slots=BoundedSemaphore(1)

def extract_resume(raw:bytes, filename:str):
    name=(filename or '').lower()
    if not raw: raise HTTPException(422,'The file is empty.')
    if len(raw)>MAX_BYTES: raise HTTPException(413,'File must be no larger than 5 MB.')
    if name.endswith('.pdf') and raw.startswith(b'%PDF-'): kind='pdf'
    elif name.endswith('.docx') and raw.startswith(b'PK\x03\x04'): kind='docx'
    else: raise HTTPException(415,'Only valid PDF and DOCX files are supported.')
    if not _slots.acquire(blocking=False):
        raise HTTPException(503,'The file processor is busy. Please retry.',headers={'Retry-After':'10'})
    try:
        root=str(Path(__file__).resolve().parents[2])
        # Don't pass database credentials or Gemini keys to the extraction worker.
        env={'PATH':os.environ.get('PATH',''), 'PYTHONPATH':root, 'PYTHONIOENCODING':'utf-8', 'LANG':'C.UTF-8'}
        try:
            proc=subprocess.run([sys.executable,'-m','app.services.resume_extract_worker',kind],input=raw,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=12, cwd=root, env=env,check=False)
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(422,'The file took too long to process. Please use a simpler PDF or DOCX.') from exc
        try: result=json.loads(proc.stdout)
        except (ValueError, UnicodeDecodeError): raise HTTPException(422,'Could not safely process this file. Try a simpler PDF or DOCX.')
        if proc.returncode or not isinstance(result,dict): raise HTTPException(422,'Could not safely process this file.')
        if 'error' in result: raise HTTPException(422,result['error'])
        if not isinstance(result.get('text'),str): raise HTTPException(422,'Could not extract text from this file.')
        return result
    finally:
        _slots.release()
