import os, json, requests
BASE="https://api.avito.ru"

def get_avito_accounts():
    accounts=[]
    for key in ["AVITO_ACCOUNTS_JSON"]+[f"AVITO_ACCOUNTS_JSON_{i}" for i in range(1,21)]:
        value=os.getenv(key)
        if not value: continue
        try:
            parsed=json.loads(value)
            if isinstance(parsed,list): accounts.extend(parsed)
        except Exception as e:
            print(f"[ASO] Error parsing {key}: {e}")
    unique={}
    for acc in accounts:
        cid=acc.get("client_id")
        if cid: unique[cid]=acc
    return list(unique.values())

def safe_account(acc):
    return {"name":acc.get("name"),"client_id_tail":acc.get("client_id","")[-4:],"has_secret":bool(acc.get("client_secret"))}

def accounts_status():
    accs=get_avito_accounts()
    return {"configured_count":len(accs),"accounts":[safe_account(a) for a in accs]}

def find_account(name=None):
    accs=get_avito_accounts()
    if not accs: return None
    if not name: return accs[0]
    return next((a for a in accs if a.get("name")==name),None)

def avito_token(account):
    if not account: return {"ok":False,"error":"account_not_found"}
    try:
        r=requests.post(f"{BASE}/token",data={"grant_type":"client_credentials","client_id":account.get("client_id"),"client_secret":account.get("client_secret")},timeout=25)
        try: data=r.json()
        except Exception: data={"raw":r.text}
        return {"ok":r.ok,"status_code":r.status_code,"data":data}
    except Exception as e:
        return {"ok":False,"error":str(e)}

def get_access_token(account):
    t=avito_token(account)
    if not t.get("ok"): return None,t
    token=t.get("data",{}).get("access_token")
    if not token: return None,{"ok":False,"error":"no_access_token","token_response":t}
    return token,t

def api_get(account,path,params=None):
    token,t=get_access_token(account)
    if not token: return t
    try:
        r=requests.get(f"{BASE}{path}",headers={"Authorization":f"Bearer {token}"},params=params or {},timeout=25)
        try: data=r.json()
        except Exception: data={"raw":r.text}
        return {"ok":r.ok,"status_code":r.status_code,"account":account.get("name"),"path":path,"data":data}
    except Exception as e:
        return {"ok":False,"account":account.get("name"),"path":path,"error":str(e)}

def test_all_tokens():
    res=[]
    for acc in get_avito_accounts():
        t=avito_token(acc)
        res.append({"account":acc.get("name"),"ok":t.get("ok"),"status_code":t.get("status_code"),"error":t.get("error"),"api_error":t.get("data",{}).get("error") if isinstance(t.get("data"),dict) else None})
    return {"accounts_tested":len(res),"results":res}

def avito_self(account):
    return api_get(account,"/core/v1/accounts/self")

def normalize_list(data):
    if isinstance(data,list): return data
    if isinstance(data,dict):
        for key in ["responses","negotiations","applicants","applications","items","result","data","vacancies","resumes","chats"]:
            val=data.get(key)
            if isinstance(val,list): return val
            if isinstance(val,dict):
                inner=normalize_list(val)
                if inner: return inner
    return []

def preview(data,n=900):
    try: return json.dumps(data,ensure_ascii=False)[:n]
    except Exception: return str(data)[:n]

def candidate_paths(account_id=None):
    paths=[
        "/job/v1/responses","/job/v1/negotiations","/job/v1/applications",
        "/job/v2/responses","/job/v2/negotiations","/job/v2/applications",
        "/vacancy/v1/responses","/vacancy/v1/negotiations",
        "/jobs/v1/responses","/jobs/v1/negotiations",
        "/core/v1/items"
    ]
    if account_id:
        paths=[
            f"/job/v1/accounts/{account_id}/responses",f"/job/v1/accounts/{account_id}/negotiations",f"/job/v1/accounts/{account_id}/applications",
            f"/job/v2/accounts/{account_id}/responses",f"/job/v2/accounts/{account_id}/negotiations",f"/jobs/v1/accounts/{account_id}/responses",
            f"/messenger/v2/accounts/{account_id}/chats"
        ]+paths
    return paths

def discover_vacancy_endpoints(account,limit=5):
    self_data=avito_self(account)
    account_id=self_data.get("data",{}).get("id") if self_data.get("ok") else None
    results=[]
    for path in candidate_paths(account_id):
        raw=api_get(account,path,{"limit":limit,"per_page":limit})
        items=normalize_list(raw.get("data",{}))
        results.append({"path":path,"ok":raw.get("ok"),"status_code":raw.get("status_code"),"items_found":len(items),"preview":preview(raw.get("data",{})),"error":raw.get("error")})
    return {"account":account.get("name") if account else None,"account_id":account_id,"results":results}

def discover_all(limit=5,max_accounts=3):
    out=[]
    for acc in get_avito_accounts()[:max_accounts]:
        out.append(discover_vacancy_endpoints(acc,limit))
    return {"accounts_checked":len(out),"results":out}

def get_responses_for_account(account,limit=50):
    self_data=avito_self(account)
    account_id=self_data.get("data",{}).get("id") if self_data.get("ok") else None
    attempts=[]
    for path in candidate_paths(account_id):
        raw=api_get(account,path,{"limit":limit,"per_page":limit})
        items=normalize_list(raw.get("data",{}))
        attempts.append({"path":path,"ok":raw.get("ok"),"status_code":raw.get("status_code"),"items_found":len(items),"preview":preview(raw.get("data",{}),350)})
        if raw.get("ok") and items:
            return {"ok":True,"account":account.get("name"),"path":path,"items":items,"attempts":attempts}
    return {"ok":False,"account":account.get("name"),"items":[],"attempts":attempts}

def deep_find(obj, key_contains):
    if isinstance(obj,dict):
        for k,v in obj.items():
            if key_contains in str(k).lower():
                return v
            found=deep_find(v,key_contains)
            if found: return found
    if isinstance(obj,list):
        for x in obj:
            found=deep_find(x,key_contains)
            if found: return found
    return None

def extract_phone(obj):
    val=deep_find(obj,"phone")
    if isinstance(val,str): return val
    if isinstance(val,list) and val:
        first=val[0]
        if isinstance(first,str): return first
        if isinstance(first,dict): return first.get("value") or first.get("phone") or first.get("number")
    if isinstance(val,dict): return val.get("value") or val.get("phone") or val.get("number")
    return None

def extract_name(obj):
    for key in ["name","fio","full_name","title"]:
        val=deep_find(obj,key)
        if isinstance(val,str) and val: return val
    return "Avito Candidate"

def response_to_candidate_payload(item,account_name="avito"):
    response_id=str(item.get("id") or item.get("response_id") or item.get("negotiation_id") or item.get("application_id") or "")
    vacancy=item.get("vacancy") or item.get("item") or {}
    vacancy_id=str(item.get("vacancy_id") or vacancy.get("id") or item.get("item_id") or "")
    chat=item.get("chat") or {}
    chat_id=str(item.get("chat_id") or chat.get("id") or "")
    return {"phone":extract_phone(item),"name":extract_name(item),"source":"avito_response:"+account_name,"external_id":response_id or chat_id or vacancy_id,"avito_chat_id":chat_id,"avito_vacancy_id":vacancy_id,"avito_response_id":response_id,"last_dialogue":json.dumps(item,ensure_ascii=False)[:4000],"consent":False,"do_not_contact":False}
