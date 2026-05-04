from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import re
import time
import hmac
import hashlib

app = FastAPI()

# 🔐 CONFIG (mover a env en producción)
SECRET = "supersecret"
RATE_LIMIT = 5  # requests por minuto

# 🧠 storage temporal (luego DB)
users = {}
rate_store = {}

# 🌐 CORS (reemplazar por tu dominio real)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # luego cambiar a tu dominio Vercel
    allow_methods=["POST"],
    allow_headers=["*"],
)

# -----------------------------
# 📦 MODELOS
# -----------------------------

class RegisterInput(BaseModel):
    phone: str = Field(..., min_length=6)
    lat: float | None = None
    lon: float | None = None

# -----------------------------
# 🔧 HELPERS
# -----------------------------

def normalize_phone(phone: str):
    digits = re.sub(r"\D", "", phone)

    if len(digits) < 8:
        raise ValueError("invalid phone")

    if not digits.startswith("54"):
        digits = "54" + digits

    return "+" + digits


def is_rate_limited(phone: str):
    now = time.time()
    window = 60

    if phone not in rate_store:
        rate_store[phone] = []

    rate_store[phone] = [
        t for t in rate_store[phone] if now - t < window
    ]

    if len(rate_store[phone]) >= RATE_LIMIT:
        return True

    rate_store[phone].append(now)
    return False


def verify_signature(body: bytes, signature: str):
    computed = hmac.new(
        SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed, signature)


async def send_sms(phone: str, message: str):
    # 🔴 reemplazar con proveedor real (Infobip, etc)
    print(f"[SMS] {phone}: {message}")

# -----------------------------
# 🚀 ENDPOINTS
# -----------------------------

@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/register")
async def register(data: RegisterInput):
    try:
        phone = normalize_phone(data.phone)
    except:
        raise HTTPException(status_code=400, detail="invalid phone")

    if is_rate_limited(phone):
        raise HTTPException(status_code=429, detail="rate limited")

    users[phone] = {
        "lat": data.lat,
        "lon": data.lon,
        "active": False,
        "confirmed": False
    }

    await send_sms(
        phone,
        "AgroAlert: respondé SI para activar alertas o STOP para cancelar"
    )

    return {"status": "ok"}


@app.post("/sms/incoming")
async def incoming_sms(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Signature", "")

    if not verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="invalid signature")

    data = await request.json()
    phone = data.get("from")
    text = data.get("text", "").strip().upper()

    if not phone or not text:
        raise HTTPException(status_code=400)

    if is_rate_limited(phone):
        return {"status": "rate_limited"}

    # si no existe → ignorar
    if phone not in users:
        return {"status": "unknown user"}

    # STOP
    if text == "STOP":
        users[phone]["active"] = False
        await send_sms(phone, "Te desuscribiste correctamente")
        return {"status": "unsubscribed"}

    # SI
    if text == "SI":
        users[phone]["active"] = True
        users[phone]["confirmed"] = True
        await send_sms(phone, "Suscripción activada ✅")
        return {"status": "subscribed"}

    # si no está activo
    if not users[phone]["active"]:
        return {"status": "inactive"}

    # comandos
    if text == "HELADA":
        await send_sms(
            phone,
            "❄️ Helada probable 70% (SMN + modelo externo)"
        )
    elif text == "LLUVIA":
        await send_sms(
            phone,
            "🌧️ Próximas 24h: 20mm estimados"
        )
    else:
        await send_sms(
            phone,
            "Comando no reconocido"
        )

    return {"status": "ok"}
