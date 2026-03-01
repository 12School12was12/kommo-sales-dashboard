import os
import json
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kommo Webhook Server")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
KOMMO_SUBDOMAIN = os.environ.get("KOMMO_SUBDOMAIN", "letofacultetschool")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

MANAGERS = {
    11891519: "Student Coordinator",
    13679767: "Asel",
    13689299: "Iaroslava",
    13777559: "Anastasiia",
    13940623: "Elizabeth",
    13993735: "Nicole",
    14067820: "Alfiia",
    14067824: "Alina",
    14679516: "Iana",
    14867844: "Irina",
    14867848: "Diana",
}

@app.get("/")
async def root():
    return {"status": "ok", "service": "Kommo Webhook Server"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/webhook/kommo")
async def kommo_webhook(request: Request):
    try:
        data = await request.form()
        payload = dict(data)
    except Exception:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
    logger.info(f"Webhook received, keys: {list(payload.keys())}")
    await process_webhook(payload)
    return JSONResponse({"status": "ok"})

async def process_webhook(payload: dict):
    try:
        for direction, key in [("incoming", "message"), ("outgoing", "outgoing_chat_message")]:
            if key in payload:
                msgs = payload[key].get("add", [])
                for msg in (msgs if isinstance(msgs, list) else [msgs]):
                    await save_message(msg, direction)
        if "leads" in payload:
            for action in ["add", "update"]:
                if action in payload["leads"]:
                    leads = payload["leads"][action]
                    for lead in (leads if isinstance(leads, list) else [leads]):
                        await save_lead(lead)
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")

async def save_message(msg: dict, direction: str):
    try:
        lead_id = msg.get("lead_id") or msg.get("entity_id")
        if not lead_id:
            return
        manager_id = msg.get("responsible_user_id") or msg.get("author_id")
        manager_name = MANAGERS.get(int(manager_id)) if manager_id else None
        created_ts = msg.get("created_at") or msg.get("date_create")
        if isinstance(created_ts, (int, float)):
            created_at = datetime.fromtimestamp(created_ts).isoformat()
        else:
            created_at = datetime.now().isoformat()
        text = (msg.get("text") or msg.get("body") or msg.get("content", "")).strip()
        channel = str(msg.get("origin") or msg.get("channel") or "unknown")
        record = {
            "kommo_lead_id": int(lead_id),
            "kommo_talk_id": msg.get("talk_id"),
            "manager_id": int(manager_id) if manager_id else None,
            "manager_name": manager_name,
            "direction": direction,
            "message_text": text or None,
            "channel": channel,
            "created_at": created_at,
        }
        supabase.table("messages").insert(record).execute()
        logger.info(f"Saved {direction} message for lead {lead_id}")
    except Exception as e:
        logger.error(f"Error saving message: {e}")

async def save_lead(lead: dict):
    try:
        lead_id = lead.get("id")
        if not lead_id:
            return
        responsible_id = lead.get("responsible_user_id")
        record = {
            "id": int(lead_id),
            "name": lead.get("name"),
            "status_id": lead.get("status_id"),
            "pipeline_id": lead.get("pipeline_id"),
            "responsible_user_id": int(responsible_id) if responsible_id else None,
            "responsible_user_name": MANAGERS.get(int(responsible_id)) if responsible_id else None,
            "updated_at": datetime.now().isoformat(),
        }
        supabase.table("leads").upsert(record).execute()
    except Exception as e:
        logger.error(f"Error saving lead: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
