"""Admin tool: remove ALL Adzuna snapshots and matching history, across users.

Run only after database backup and explicit confirmation. See PHASE5_SOURCES.md.
"""
import sys
from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.db.session import get_engine
from app.models import JobMatchReport,JobSourceCache,SavedJob

def main():
    if sys.argv[1:]!=['--confirm-delete-all-adzuna']:
        print('No changes made. Back up first. Pass --confirm-delete-all-adzuna to remove cached, saved and matched Adzuna data for ALL users.')
        return 2
    with Session(get_engine()) as db:
        counts=[]
        for model in (JobSourceCache,SavedJob,JobMatchReport):
            result=db.execute(delete(model).where(model.job_key.like('adzuna~%')))
            counts.append(result.rowcount)
        db.commit()
    print('Removed cache rows, saved jobs, and match reports:',counts)
    return 0
if __name__=='__main__':raise SystemExit(main())
