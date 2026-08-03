# DalaBozor — Backend (FastAPI + PostgreSQL)

Dehqonni restoran bilan bog'laydigan B2B agro-marketplace API'si.
Daromad modeli: **marja** (olish ↔ sotish narxi farqi), to'lov komissiyasi emas.

## Stack
- Python 3.11+, FastAPI, Uvicorn
- PostgreSQL 15 + SQLAlchemy 2.0 (async) + Alembic
- Pydantic v2, JWT (telefon + OTP, parolsiz)
- APScheduler (21:00 allocation, 12:00 payout)

## Tez ishga tushirish

```bash
cd backend

# 1) Virtual muhit
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Postgres (Docker)
docker compose up -d          # port 5440 (host 5432/5433 band bo'lsa)

# 3) .env tayyorlash
cp .env.example .env
# CARD_ENCRYPTION_KEY yaratish:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# JWT_SECRET yaratish:
python -c "import secrets; print(secrets.token_urlsafe(48))"
# ikkalasini .env ga qo'ying

# 4) Migratsiya
alembic upgrade head

# 5) Seed (test ma'lumot)
python -m app.seed

# 6) Ishga tushirish
uvicorn app.main:app --reload --port 8099
```

Swagger: http://127.0.0.1:8099/docs · Health: `/health`

## Auth oqimi (dev)
`.env` da `ENV=dev` va `OTP_DEV_CODE=1111` bo'lsa, kod doim **1111**.

```bash
B=http://127.0.0.1:8099/api/v1
curl -X POST $B/auth/request-otp -d '{"phone":"+998900000001"}' -H 'Content-Type: application/json'
curl -X POST $B/auth/verify-otp  -d '{"phone":"+998900000001","code":"1111"}' -H 'Content-Type: application/json'
# access_token bilan:
curl $B/auth/me -H "Authorization: Bearer <TOKEN>"
```

## Loyiha tuzilmasi
```
app/
  main.py            FastAPI ilova + lifespan (scheduler)
  core/              config, db (async), security (JWT/Fernet/HMAC), deps (require_role)
  models/            SQLAlchemy modellar + enums
  schemas/           Pydantic sxemalar
  api/v1/            routerlar (auth, farmer, ...)
  services/          biznes-mantiq (auth, corridor, sms, allocation, payout)
  adapters/          sms (mock/eskiz), payment (mock/payme/click)
  jobs/              scheduler (cron)
  seed.py            test ma'lumot
alembic/             migratsiyalar
tests/               pytest
docker-compose.yml   Postgres 15
```

## Holat (fazalar) — ✅ TO'LIQ TAYYOR
- [x] **Faza 0** — poydevor (config/db/security/alembic/docker)
- [x] **Faza 1** — auth (OTP + JWT) + rollar + require_role
- [x] **Faza 2** — offer + narx koridori (auto_approved / needs_review)
- [x] **Faza 3** — restoran (order + katalog + invoice PDF)
- [x] **Faza 4** — yig'uvchi + allocation (21:00) + payout (12:00) + APScheduler
- [x] **Faza 5** — admin + to'lov (Mock adapter; Payme/Click slot)
- [x] **Faza 6** — pytest (11 test o'tdi)

**Sinov:** butun kunlik sikl (e'lon → buyurtma → taqsimot → yig'im → payout) E2E o'tkazildi.
`pytest -q` → 11 passed.

## Kunlik sikl endpointlari
- Dehqon: `/prices/today`, `/offers`, `/offers/mine`, `/farmers/me/balance`
- Restoran: `/catalog`, `/orders`, `/orders/{id}` (timeline), `/orders/{id}/invoice` (PDF), `/orders/{id}/reorder`
- Yig'uvchi: `/routes/today`, `/stops/{id}/accept`, `/offers/on-behalf`
- Admin: `/admin/dashboard`, `/admin/corridor/today`, `/admin/offers/{id}/review`, `/admin/calls`, `/admin/allocation/run`, `/admin/payouts/run`
- To'lov: `/cards`, `/payments/invoice`, `/payments/payout`

## DalaYordamchi AI

Barcha AI endpointlari Bearer token talab qiladi:

- `GET /api/v1/ai/status` — chat sozlanganini ko'rsatadi, kalitni hech qachon
  qaytarmaydi.
- `POST /api/v1/ai/chat` — Groq orqali rol va ochiq sahifaga mos o'zbekcha
  yordam beradi.

`.env` ichiga faqat yangi, rotatsiya qilingan server kalitlarini yozing:

```env
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
```

Bu kalitlarni frontendga, `NEXT_PUBLIC_*` o'zgaruvchisiga yoki git tarixiga
joylamang. AI yaratgan `navigate`, `switch_role`, `add_role`, `remove_role`
actionlari server allowlistidan o'tadi va har doim UI tasdig'ini talab qiladi.

## Xavfsizlik
- Karta to'liq raqami/CVV/expiry **hech qachon** saqlanmaydi — faqat token (Fernet).
- OTP kodi HMAC-SHA256 bilan hashlanadi.
- Har himoyalangan endpointda `require_role(...)` dependency.
- Self-service orqali faqat dehqon/restoran roli qo'shiladi; collector va admin
  rollarini tizim administratori biriktiradi.
- Yig'uvchi faqat o'ziga biriktirilgan marshrut stopini qabul qila oladi.
- Chat konteksti va provider timeouti cheklangan; AI actionlari server
  allowlistidan o'tadi.
- SMS/To'lov — adapter pattern (Mock dev, prod slot bo'sh).
