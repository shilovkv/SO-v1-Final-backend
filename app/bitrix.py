import os
def configured():
    return bool(os.getenv("BITRIX_WEBHOOK_URL"))
