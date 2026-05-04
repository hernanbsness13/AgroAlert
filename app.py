from fastapi import FastAPI, Request
import hmac, hashlib, time

app = FastAPI()

SECRET = "supersecret"
rate_store = {}

def verify_signature(body, signature):
    computed = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)

def is_rate_limited(phone):
    now = time.time()
    window = 60

    if phone not in rate_store:
        rate_store[phone] = []

    rate_store[phone] = [t for t in rate_store[phone] if now - t < window]

    if len(rate_store[phone]) >= 5:
        return True

    rate_store[phone].append(now)
    return False

@app.post("/sms/incoming")
async def incoming(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Signature", "")

    if not verify_signature(body, signature):
        return {"error": "invalid signature"}

    data = await request.json()
    phone = data.get("from")
    text = data.get("text", "").upper()

    if is_rate_limited(phone):
        return {"status": "rate limited"}

    if text == "STOP":
        return {"reply": "Te desuscribiste correctamente"}

    if text == "SI":
        return {"reply": "Suscripción activada"}

    if text == "HELADA":
        return {"reply": "❄️ Helada probable 70% (SMN + modelo)"}

    return {"reply": "Comando no reconocido"}
