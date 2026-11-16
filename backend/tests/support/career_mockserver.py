"""LOCAL TEST ONLY: fictional AI; never deploy this as your application server."""
from tests.support.mockserver import app
from app.services import career

def fake_plan(goal,evidence,weeks):
    return {'summary':'Fictional test roadmap.','evidence_limitations':'Test evidence only.',
      'skills':[{'name':'React','category':'missing','level':'beginner','priority':'high','estimated_hours':10,'rationale':'Practice this skill.'}],
      'weeks':[{'week':i,'theme':'Practice foundations','tasks':[{'day':d,'title':f'Practice day {d}','description':'Build and practice a small example.','estimated_minutes':60,'difficulty':'beginner','skill':'React','resource_ids':['react']} for d in range(1,8)]} for i in range(1,weeks+1)]}
career.generate=fake_plan
career.mentor=lambda goal,roadmap,question:'Mock mentor: practice a small React example.'
