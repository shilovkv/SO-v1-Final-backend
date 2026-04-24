from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from .db import Base, engine, get_db
from .models import Agent, Task, Memory, Candidate, Campaign
from . import avito, bitrix

Base.metadata.create_all(bind=engine)
app=FastAPI(title="ASO v1.1 Final — Avito Vacancy Responses",version="1.1.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

class CandidateCreate(BaseModel):
    phone: Optional[str]=None; name: Optional[str]=None; city: Optional[str]=None; age: Optional[int]=None; source:str="manual"; external_id:Optional[str]=None; bitrix_status:Optional[str]=None; avito_chat_id:Optional[str]=None; avito_vacancy_id:Optional[str]=None; avito_response_id:Optional[str]=None; last_dialogue:Optional[str]=None; consent:bool=False; do_not_contact:bool=False
class CandidateImport(BaseModel): candidates:List[CandidateCreate]
class SMSCampaignPrepare(BaseModel):
    name:str="Contract Candidate Test 100"; size:int=100; message:str="Здравствуйте! Вы ранее оставляли отклик по службе по контракту. Можем бесплатно уточнить актуальность и подсказать порядок действий. Ответьте 1, если актуально, 0 — если больше не писать."

def remember(db,event_type,content):
    m=Memory(event_type=event_type,content=content); db.add(m); db.commit(); return m

def candidate_to_dict(c):
    return {"id":c.id,"phone":c.phone,"name":c.name,"source":c.source,"external_id":c.external_id,"avito_chat_id":c.avito_chat_id,"avito_vacancy_id":c.avito_vacancy_id,"avito_response_id":c.avito_response_id,"consent":c.consent,"do_not_contact":c.do_not_contact,"segment":c.segment,"status":c.status,"next_action":c.next_action,"risk_flag":c.risk_flag}

def segment_candidate(c):
    text=((c.bitrix_status or "")+" "+(c.last_dialogue or "")).lower()
    if c.do_not_contact: return "Do Not Contact","Stopped","none","do_not_contact"
    if not c.consent: return "Consent Needed","Hold","request/check consent","no_consent"
    if any(x in text for x in ["не интересно","не звонить","отказ","не писать","stop","0"]): return "Do Not Contact","Stopped","none","refusal_detected"
    if any(x in text for x in ["перезвон","актуально","готов","хочу","когда","документы","1"]): return "Hot","Call Needed","call candidate",None
    if any(x in text for x in ["условия","выплаты","документы","возраст","город","военный билет"]): return "Need Info","SMS Needed","send info sms",None
    return "Warm","SMS Needed","send actuality sms",None

def upsert_candidate(db,payload):
    phone=payload.get("phone"); external_id=payload.get("external_id")
    c=None
    if phone: c=db.query(Candidate).filter(Candidate.phone==phone).first()
    if not c and external_id: c=db.query(Candidate).filter(Candidate.external_id==external_id).first()
    if c:
        for k,v in payload.items():
            if v is not None and hasattr(c,k): setattr(c,k,v)
        c.segment,c.status,c.next_action,c.risk_flag=segment_candidate(c); db.commit(); db.refresh(c); return c,"updated"
    if not phone and not external_id: return None,"no_identifier"
    c=Candidate(**payload); c.segment,c.status,c.next_action,c.risk_flag=segment_candidate(c)
    db.add(c); db.commit(); db.refresh(c); return c,"created"

@app.get("/")
def root(): return {"system":"ASO","version":"1.1.0","status":"online","docs":"/docs"}
@app.get("/health")
def health(): return {"status":"ok","version":"1.1.0"}
@app.get("/integrations/avito/accounts")
def avito_accounts(): return avito.accounts_status()
@app.post("/integrations/avito/test-token")
def avito_test_token(): return avito.test_all_tokens()
@app.post("/integrations/avito/get-self")
def avito_get_self(account_name:Optional[str]=None): return avito.avito_self(avito.find_account(account_name))
@app.post("/integrations/avito/discover-vacancy-endpoints")
def avito_discover_vacancy_endpoints(limit:int=5,max_accounts:int=3): return avito.discover_all(limit,max_accounts)

@app.post("/integrations/avito/sync-vacancy-responses")
def avito_sync_vacancy_responses(limit:int=50,max_accounts:int=61,db:Session=Depends(get_db)):
    created=updated=skipped=0; results=[]; preview=[]
    for acc in avito.get_avito_accounts()[:max_accounts]:
        data=avito.get_responses_for_account(acc,limit); items=data.get("items",[])
        ac=au=as_=0
        for item in items:
            payload=avito.response_to_candidate_payload(item,acc.get("name"))
            c,status=upsert_candidate(db,payload)
            if status=="created": created+=1; ac+=1
            elif status=="updated": updated+=1; au+=1
            else: skipped+=1; as_+=1
            if c and len(preview)<20: preview.append(candidate_to_dict(c))
        results.append({"account":acc.get("name"),"ok":data.get("ok"),"items_found":len(items),"created":ac,"updated":au,"skipped":as_,"attempts":data.get("attempts",[])[:8]})
    remember(db,"avito.responses.sync",f"created={created} updated={updated} skipped={skipped}")
    return {"accounts_processed":min(max_accounts,len(avito.get_avito_accounts())),"created":created,"updated":updated,"skipped":skipped,"results":results,"imported_preview":preview}

@app.post("/integrations/avito/sync-all-chats")
def avito_sync_all_chats(limit:int=50):
    return {"status":"deprecated_for_this_business","reason":"Use /integrations/avito/sync-vacancy-responses. Messenger chats returned 400 for connected accounts.","limit":limit}

@app.post("/companyos/run-autonomous-cycle")
def run_autonomous_cycle(db:Session=Depends(get_db)):
    for title,owner,layer in [("Discover Avito vacancy endpoints","AI IT Agent","CompanyOS"),("Sync Avito vacancy responses","AI Avito Operator Agent","CompanyOS"),("Segment candidates","AI ROP Agent","CandidateOS"),("Prepare SMS test 100","AI Candidate Manager Agent","CandidateOS"),("Review consent and Do Not Contact","AI Compliance Agent","Governance")]:
        db.add(Task(title=title,owner=owner,layer=layer,status="queued",progress=10))
    db.commit(); remember(db,"companyos.cycle","v1.1 cycle queued")
    return {"status":"queued","tasks":["Discover Avito vacancy endpoints","Sync Avito vacancy responses","Segment candidates","Prepare SMS test 100","Review consent and Do Not Contact"]}

@app.post("/candidates/import")
def import_candidates(payload:CandidateImport,db:Session=Depends(get_db)):
    out=[]
    for item in payload.candidates:
        c,status=upsert_candidate(db,item.model_dump())
        if c: out.append({"status":status,"candidate":candidate_to_dict(c)})
    return {"processed":len(out),"results":out}
@app.post("/candidates/segment")
def segment_candidates(db:Session=Depends(get_db)):
    rows=db.query(Candidate).all(); summary={}
    for c in rows:
        c.segment,c.status,c.next_action,c.risk_flag=segment_candidate(c); summary[c.segment]=summary.get(c.segment,0)+1
    db.commit(); return {"segmented":len(rows),"summary":summary}
@app.get("/candidates")
def list_candidates(segment:Optional[str]=None,limit:int=100,db:Session=Depends(get_db)):
    q=db.query(Candidate)
    if segment: q=q.filter(Candidate.segment==segment)
    return [candidate_to_dict(c) for c in q.order_by(Candidate.id.desc()).limit(limit).all()]
@app.post("/campaigns/prepare-sms-test")
def prepare_sms_test(payload:SMSCampaignPrepare,db:Session=Depends(get_db)):
    eligible=db.query(Candidate).filter(Candidate.consent==True,Candidate.do_not_contact==False,Candidate.segment.in_(["Hot","Warm","Need Info"])).limit(payload.size).all()
    camp=Campaign(name=payload.name,channel="SMS",size=len(eligible),status="prepared",message=payload.message); db.add(camp); db.commit(); db.refresh(camp)
    return {"campaign":{"id":camp.id,"name":camp.name,"size":camp.size,"status":camp.status,"message":camp.message},"eligible_candidates":[candidate_to_dict(c) for c in eligible]}
@app.get("/aso/state")
def aso_state(db:Session=Depends(get_db)):
    return {"agents":db.query(Agent).count(),"tasks":db.query(Task).count(),"candidates":db.query(Candidate).count(),"campaigns":db.query(Campaign).count(),"candidate_segments":{"Hot":db.query(Candidate).filter(Candidate.segment=="Hot").count(),"Warm":db.query(Candidate).filter(Candidate.segment=="Warm").count(),"Need Info":db.query(Candidate).filter(Candidate.segment=="Need Info").count(),"Consent Needed":db.query(Candidate).filter(Candidate.segment=="Consent Needed").count(),"Do Not Contact":db.query(Candidate).filter(Candidate.segment=="Do Not Contact").count()},"integrations":{"avito_accounts":avito.accounts_status().get("configured_count"),"bitrix_configured":bitrix.configured()}}
@app.get("/memory")
def read_memory(db:Session=Depends(get_db)): return db.query(Memory).order_by(Memory.id.desc()).limit(50).all()
