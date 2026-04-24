import os, json, requests

def get_avito_accounts():
    raw = os.getenv("AVITO_ACCOUNTS_JSON", "[]")
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [a for a in data if a.get("client_id") and a.get("client_secret")]
    except Exception:
        return []
    return []

def safe_account(a):
    return {
        "name": a.get("name"),
        "client_id_tail": str(a.get("client_id",""))[-4:],
        "has_secret": bool(a.get("client_secret"))
    }

def find_account(name=None):
    accounts = get_avito_accounts()
    if not name:
        return accounts[0] if accounts else None
    for a in accounts:
        if a.get("name") == name:
            return a
    return None

def avito_token(account):
    try:
        r = requests.post(
            "https://api.avito.ru/token",
            data={
                "grant_type": "client_credentials",
                "client_id": account["client_id"],
                "client_secret": account["client_secret"]
            },
            timeout=25
        )
        return {"ok": r.ok, "status_code": r.status_code, "data": r.json()}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def avito_get(account, path):
    token = avito_token(account)
    if not token.get("ok"):
        return token
    access_token = token.get("data", {}).get("access_token")
    if not access_token:
        return {"ok": False, "error": "No access_token", "raw": token}
    try:
        r = requests.get("https://api.avito.ru" + path, headers={"Authorization": "Bearer " + access_token}, timeout=25)
        try:
            data = r.json()
        except Exception:
            data = r.text
        return {"ok": r.ok, "status_code": r.status_code, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def avito_self(account):
    return avito_get(account, "/core/v1/accounts/self")

def extract_user_id(self_result):
    data = self_result.get("data")
    if isinstance(data, dict):
        for key in ["id", "user_id", "account_id"]:
            if data.get(key):
                return str(data.get(key))
        if isinstance(data.get("result"), dict):
            for key in ["id", "user_id", "account_id"]:
                if data["result"].get(key):
                    return str(data["result"].get(key))
    return None

def avito_chats(account, limit=50):
    self_result = avito_self(account)
    user_id = extract_user_id(self_result)
    if not user_id:
        return {"ok": False, "error": "Could not determine Avito user_id", "self_result": self_result}
    result = avito_get(account, f"/messenger/v2/accounts/{user_id}/chats?limit={limit}")
    result["user_id"] = user_id
    return result

def normalize_chats(raw):
    data = raw.get("data")
    if isinstance(data, dict):
        for key in ["chats", "items", "result"]:
            if isinstance(data.get(key), list):
                return data.get(key)
        if isinstance(data.get("result"), dict):
            for key in ["chats", "items"]:
                if isinstance(data["result"].get(key), list):
                    return data["result"].get(key)
    if isinstance(data, list):
        return data
    return []

def chat_to_candidate_payload(account_name, user_id, chat):
    chat_id = str(chat.get("id") or chat.get("chat_id") or chat.get("chatId") or "")
    user = chat.get("user") or chat.get("buyer") or chat.get("participant") or {}
    phone = user.get("phone") or chat.get("phone")
    name = user.get("name") or user.get("title") or chat.get("title") or chat.get("name")
    return {
        "phone": phone,
        "name": name,
        "source": "avito",
        "account_name": account_name,
        "external_id": chat_id,
        "avito_user_id": str(user_id) if user_id else None,
        "avito_chat_id": chat_id,
        "last_dialogue": json.dumps(chat, ensure_ascii=False)[:5000],
        "consent": False,
        "do_not_contact": False
    }
