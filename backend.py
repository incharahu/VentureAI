from urllib.parse import quote_plus
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

DB_URL = f"mysql+pymysql://root:{quote_plus('Inchara@123#')}@localhost:3306/ventureai_db"
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
"""
╔══════════════════════════════════════════════════════════════╗
║   VentureAI — AI Based Global Startup Networking Platform    ║
║   Backend  ·  Python FastAPI  ·  MySQL Database              ║
╠══════════════════════════════════════════════════════════════╣
║  INSTALL:                                                     ║
║    pip install fastapi uvicorn pymysql sqlalchemy             ║
║    pip install python-jose passlib[bcrypt] cryptography       ║
║    pip install python-multipart aiofiles openai               ║
║                                                               ║
║  MYSQL SETUP (run in MySQL Workbench):                        ║
║    CREATE DATABASE ventureai_db;                              ║
║                                                               ║
║  RUN:   python backend.py                                     ║
║  OPEN:  http://localhost:8000                                 ║
║  DOCS:  http://localhost:8000/docs                            ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import (create_engine, Column, Integer, String,
    Float, Boolean, Text, DateTime, ForeignKey, JSON)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

MYSQL_USER     = "root"
MYSQL_PASSWORD = "Inchara@123#"
MYSQL_HOST     = "localhost"
MYSQL_PORT     = "3306"
MYSQL_DB       = "ventureai_db"
from urllib.parse import quote_plus
DB_URL = f"mysql+pymysql://root:{quote_plus('Inchara@123#')}@localhost:3306/ventureai_db"
SECRET_KEY  = "ventureai-jwt-secret-key-2025"
ALGORITHM   = "HS256"
TOKEN_DAYS  = 7
OPENAI_KEY  = os.getenv("OPENAI_API_KEY", "")
UPLOAD_DIR  = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────────────────────
#  DATABASE ENGINE
# ──────────────────────────────────────────────────────────────
engine      = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal= sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base        = declarative_base()

# ──────────────────────────────────────────────────────────────
#  MODELS  (each class = one MySQL table)
# ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    full_name     = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(50),  default="founder")
    country       = Column(String(100), default="")
    bio           = Column(Text,        default="")
    avatar_url    = Column(String(500), default="")
    linkedin_url  = Column(String(500), default="")
    website       = Column(String(500), default="")
    is_verified   = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    last_seen     = Column(DateTime, default=datetime.utcnow)
    startups         = relationship("Startup",        back_populates="owner")
    investor_profile = relationship("InvestorProfile",back_populates="user", uselist=False)
    connections_sent = relationship("Connection", foreign_keys="Connection.requester_id", back_populates="requester")
    connections_recv = relationship("Connection", foreign_keys="Connection.receiver_id",  back_populates="receiver")
    bookmarks        = relationship("Bookmark", back_populates="user")
    messages_sent    = relationship("Message",  foreign_keys="Message.sender_id", back_populates="sender")

class Startup(Base):
    __tablename__  = "startups"
    id             = Column(Integer, primary_key=True, index=True)
    owner_id       = Column(Integer, ForeignKey("users.id"))
    name           = Column(String(255), nullable=False)
    tagline        = Column(String(500), default="")
    description    = Column(Text,        default="")
    category       = Column(String(100), default="")
    stage          = Column(String(50),  default="Pre-Seed")
    country        = Column(String(100), default="")
    city           = Column(String(100), default="")
    website        = Column(String(500), default="")
    logo_url       = Column(String(500), default="")
    pitch_deck_url = Column(String(500), default="")
    funding_ask    = Column(Float,   default=0)
    equity_offered = Column(Float,   default=0)
    current_arr    = Column(Float,   default=0)
    team_size      = Column(Integer, default=1)
    founded_year   = Column(Integer, default=2024)
    tags           = Column(JSON,    default=list)
    ai_score       = Column(Float,   default=0)
    match_score    = Column(Float,   default=0)
    views          = Column(Integer, default=0)
    is_featured    = Column(Boolean, default=False)
    is_active      = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow)
    owner          = relationship("User",     back_populates="startups")
    bookmarks      = relationship("Bookmark", back_populates="startup")

class InvestorProfile(Base):
    __tablename__    = "investor_profiles"
    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id"), unique=True)
    firm_name        = Column(String(255), default="")
    title            = Column(String(255), default="")
    aum              = Column(String(100), default="")
    check_size_min   = Column(Float, default=25000)
    check_size_max   = Column(Float, default=5000000)
    investment_focus = Column(JSON,  default=list)
    preferred_stages = Column(JSON,  default=list)
    preferred_regions= Column(JSON,  default=list)
    portfolio_count  = Column(Integer, default=0)
    deals_per_year   = Column(Integer, default=5)
    thesis           = Column(Text,    default="")
    is_verified      = Column(Boolean, default=False)
    user             = relationship("User", back_populates="investor_profile")

class Connection(Base):
    __tablename__ = "connections"
    id            = Column(Integer, primary_key=True, index=True)
    requester_id  = Column(Integer, ForeignKey("users.id"))
    receiver_id   = Column(Integer, ForeignKey("users.id"))
    status        = Column(String(50), default="pending")
    message       = Column(Text, default="")
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow)
    requester     = relationship("User", foreign_keys=[requester_id], back_populates="connections_sent")
    receiver      = relationship("User", foreign_keys=[receiver_id],  back_populates="connections_recv")

class Bookmark(Base):
    __tablename__ = "bookmarks"
    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    startup_id    = Column(Integer, ForeignKey("startups.id"))
    created_at    = Column(DateTime, default=datetime.utcnow)
    user          = relationship("User",    back_populates="bookmarks")
    startup       = relationship("Startup", back_populates="bookmarks")

class Message(Base):
    __tablename__ = "messages"
    id            = Column(Integer, primary_key=True, index=True)
    sender_id     = Column(Integer, ForeignKey("users.id"))
    receiver_id   = Column(Integer, nullable=False)
    content       = Column(Text, nullable=False)
    is_read       = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow)
    sender        = relationship("User", foreign_keys=[sender_id], back_populates="messages_sent")

class Event(Base):
    __tablename__    = "events"
    id               = Column(Integer, primary_key=True, index=True)
    organizer_id     = Column(Integer, ForeignKey("users.id"))
    title            = Column(String(255), nullable=False)
    description      = Column(Text,        default="")
    event_type       = Column(String(100), default="Networking")
    location         = Column(String(255), default="")
    is_virtual       = Column(Boolean, default=True)
    event_date       = Column(DateTime)
    max_attendees    = Column(Integer, default=100)
    tags             = Column(JSON,    default=list)
    registration_url = Column(String(500), default="")
    created_at       = Column(DateTime, default=datetime.utcnow)

class PitchAnalysis(Base):
    __tablename__     = "pitch_analyses"
    id                = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey("users.id"))
    startup_id        = Column(Integer, ForeignKey("startups.id"), nullable=True)
    file_name         = Column(String(255), default="")
    file_path         = Column(String(500), default="")
    overall_score     = Column(Float, default=0)
    market_score      = Column(Float, default=0)
    team_score        = Column(Float, default=0)
    product_score     = Column(Float, default=0)
    financials_score  = Column(Float, default=0)
    competitive_score = Column(Float, default=0)
    traction_score    = Column(Float, default=0)
    ai_feedback       = Column(Text,  default="")
    matched_investors = Column(JSON,  default=list)
    created_at        = Column(DateTime, default=datetime.utcnow)

# Create all tables automatically in MySQL
Base.metadata.create_all(bind=engine)

# ──────────────────────────────────────────────────────────────
#  PYDANTIC SCHEMAS
# ──────────────────────────────────────────────────────────────
class RegisterReq(BaseModel):
    email: str; full_name: str; password: str
    role: str = "founder"; country: str = ""

class LoginReq(BaseModel):
    email: str; password: str

class StartupCreate(BaseModel):
    name: str; tagline: str = ""; description: str = ""
    category: str = ""; stage: str = "Pre-Seed"
    country: str = ""; city: str = ""; website: str = ""
    funding_ask: float = 0; equity_offered: float = 0
    current_arr: float = 0; team_size: int = 1
    founded_year: int = 2024; tags: List[str] = []

class StartupUpdate(BaseModel):
    name: Optional[str]=None; tagline: Optional[str]=None
    description: Optional[str]=None; category: Optional[str]=None
    stage: Optional[str]=None; country: Optional[str]=None
    city: Optional[str]=None; website: Optional[str]=None
    funding_ask: Optional[float]=None; equity_offered: Optional[float]=None
    current_arr: Optional[float]=None; team_size: Optional[int]=None
    tags: Optional[List[str]]=None

class InvestorProfileCreate(BaseModel):
    firm_name: str=""; title: str=""; aum: str=""
    check_size_min: float=25000; check_size_max: float=1000000
    investment_focus: List[str]=[]; preferred_stages: List[str]=[]
    preferred_regions: List[str]=[]; deals_per_year: int=5; thesis: str=""

class ConnReq(BaseModel):
    receiver_id: int; message: str = ""

class MsgCreate(BaseModel):
    receiver_id: int; content: str

class ChatMsg(BaseModel):
    message: str; context: Optional[Dict] = {}

# ──────────────────────────────────────────────────────────────
#  SECURITY
# ──────────────────────────────────────────────────────────────
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_pw(p):   return pwd_ctx.hash(p)
def verify_pw(p, h): return pwd_ctx.verify(p, h)

def make_token(uid, role):
    exp = datetime.utcnow() + timedelta(days=TOKEN_DAYS)
    return jwt.encode({"sub": str(uid), "role": role, "exp": exp}, SECRET_KEY, ALGORITHM)

def read_token(tok):
    try: return jwt.decode(tok, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError: raise HTTPException(401, "Invalid or expired token")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

bearer = HTTPBearer(auto_error=False)

def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    if not cred: raise HTTPException(401, "Not authenticated")
    p = read_token(cred.credentials)
    u = db.query(User).filter(User.id == int(p["sub"])).first()
    if not u or not u.is_active: raise HTTPException(401, "User not found")
    u.last_seen = datetime.utcnow(); db.commit()
    return u

def optional_user(cred: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    if not cred: return None
    try:
        p = read_token(cred.credentials)
        return db.query(User).filter(User.id == int(p["sub"])).first()
    except: return None

# ──────────────────────────────────────────────────────────────
#  AI SERVICE
# ──────────────────────────────────────────────────────────────
AI_RESPONSES = {
    "match":     "Found 47 compatible investors! Top: Sequoia India 97%, a16z 94%, Lightspeed 91%. Want personalized outreach emails?",
    "pitch":     "Score: 87/100. Strong: market (91%), team (83%). Improve: competitive moat (65%) — add defensibility slide. Financials (72%) — include unit economics.",
    "investor":  "Most active this quarter: Tiger Global (Series A), Sequoia India (Seed/A - SaaS/FinTech), a16z (DeepTech). What's your stage?",
    "funding":   "2025 trends: AI/ML up 34% YoY. Avg Seed $2.1M, Series A $12.4M. Best windows: Jan-Mar and Sep-Nov.",
    "email":     "Subject: [Startup] — [Stage] Opportunity\n\nHi [Name],\nWe're building [X] for [market] with [traction]. Given your portfolio in [co], I'd love 20 mins. Available this week?",
    "market":    "Global VC: $285B in 2024. Hot sectors: AI Infrastructure +34%, Climate Tech +28%, HealthcareAI +22%.",
    "valuation": "2025 Seed: $8-12M (US), $3-6M (India). SaaS multiples: ARR x 8-15x. First-time founder discount: 30-50%.",
}

async def ai_chat(message: str, context: dict = {}) -> str:
    if OPENAI_KEY:
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=OPENAI_KEY)
            msgs = [{"role":"system","content":"You are VentureAI, an expert startup & investment advisor. Be concise and actionable."}]
            if context.get("history"): msgs.extend(context["history"][-6:])
            msgs.append({"role":"user","content":message})
            r = await client.chat.completions.create(model="gpt-4o-mini", messages=msgs, max_tokens=600)
            return r.choices[0].message.content
        except Exception as e: print(f"OpenAI error: {e}")
    low = message.lower()
    for k, v in AI_RESPONSES.items():
        if k in low: return v
    return "I can help with investor matching, pitch analysis, outreach emails, market research, and fundraising strategy. What do you need?"

async def analyze_pitch_ai(content: bytes) -> dict:
    import random; random.seed(len(content) % 100)
    s = {k: random.randint(a,b) for k,(a,b) in {
        "overall":(72,95),"market":(75,97),"team":(68,92),
        "product":(70,94),"financials":(60,88),"competitive":(55,85),"traction":(65,92)
    }.items()}
    return {
        "scores": s,
        "feedback": f"Overall {s['overall']}/100. Strong: market ({s['market']}), product-fit ({s['product']}). Improve: competitive moat ({s['competitive']}) and financial model ({s['financials']}).",
        "recommended_stage": "Series A" if s["overall"] >= 80 else "Seed",
        "investor_matches": random.randint(30, 70),
        "strengths":    ["Market sizing", "Team credentials", "Problem clarity"],
        "improvements": ["Competitive moat slide", "Unit economics", "CAC/LTV data"],
    }

def compute_match(startup: Startup, investor: InvestorProfile) -> float:
    score = 50.0
    if set((startup.tags or []) + [startup.category]) & set(investor.investment_focus or []): score += 20
    if startup.stage in (investor.preferred_stages or []): score += 15
    if startup.country in (investor.preferred_regions or []) or "Global" in (investor.preferred_regions or []): score += 10
    if investor.check_size_min <= startup.funding_ask <= investor.check_size_max: score += 5
    return min(round(score, 1), 99.0)

# ──────────────────────────────────────────────────────────────
#  APP
# ──────────────────────────────────────────────────────────────
app = FastAPI(title="VentureAI API", description="AI-powered Startup Networking & Investment Platform", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# ──────────────────────────────────────────────────────────────
#  SERIALIZERS
# ──────────────────────────────────────────────────────────────
def su(u):
    return {"id":u.id,"email":u.email,"full_name":u.full_name,"role":u.role,
            "country":u.country,"bio":u.bio,"avatar_url":u.avatar_url,
            "linkedin_url":u.linkedin_url,"website":u.website,
            "is_verified":u.is_verified,"created_at":u.created_at.isoformat()}

def ss(s):
    return {"id":s.id,"owner_id":s.owner_id,"name":s.name,"tagline":s.tagline,
            "description":s.description,"category":s.category,"stage":s.stage,
            "country":s.country,"city":s.city,"website":s.website,
            "logo_url":s.logo_url,"pitch_deck_url":s.pitch_deck_url,
            "funding_ask":s.funding_ask,"equity_offered":s.equity_offered,
            "current_arr":s.current_arr,"team_size":s.team_size,
            "founded_year":s.founded_year,"tags":s.tags or [],
            "ai_score":s.ai_score,"match_score":s.match_score,
            "views":s.views,"is_featured":s.is_featured,
            "created_at":s.created_at.isoformat()}

def si(p):
    return {"id":p.id,"user_id":p.user_id,
            "full_name":p.user.full_name if p.user else "",
            "firm_name":p.firm_name,"title":p.title,"aum":p.aum,
            "check_size_min":p.check_size_min,"check_size_max":p.check_size_max,
            "investment_focus":p.investment_focus or [],
            "preferred_stages":p.preferred_stages or [],
            "preferred_regions":p.preferred_regions or [],
            "portfolio_count":p.portfolio_count,"deals_per_year":p.deals_per_year,
            "thesis":p.thesis,"is_verified":p.is_verified}

def sc(c):
    return {"id":c.id,"requester_id":c.requester_id,"receiver_id":c.receiver_id,
            "status":c.status,"message":c.message,"created_at":c.created_at.isoformat()}

def sm(m):
    return {"id":m.id,"sender_id":m.sender_id,"receiver_id":m.receiver_id,
            "content":m.content,"is_read":m.is_read,"created_at":m.created_at.isoformat()}

def se(e):
    return {"id":e.id,"organizer_id":e.organizer_id,"title":e.title,
            "description":e.description,"event_type":e.event_type,
            "location":e.location,"is_virtual":e.is_virtual,
            "event_date":e.event_date.isoformat() if e.event_date else None,
            "max_attendees":e.max_attendees,"tags":e.tags or []}

# ──────────────────────────────────────────────────────────────
#  ROUTES
# ──────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    if Path("index.html").exists():
        return FileResponse("index.html")
    return {"app":"VentureAI","docs":"/docs","status":"running","db":"MySQL"}

@app.get("/health")
async def health(): return {"status":"healthy","db":"MySQL","time":datetime.utcnow().isoformat()}

# --- AUTH ---
@app.post("/auth/register", tags=["Auth"])
async def register(req: RegisterReq, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email.lower()).first():
        raise HTTPException(400, "Email already registered")
    u = User(email=req.email.lower(), full_name=req.full_name,
             password_hash=hash_pw(req.password), role=req.role, country=req.country)
    db.add(u); db.commit(); db.refresh(u)
    return {"access_token": make_token(u.id, u.role), "token_type":"bearer", "user": su(u)}

@app.post("/auth/login", tags=["Auth"])
async def login(req: LoginReq, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == req.email.lower()).first()
    if not u or not verify_pw(req.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not u.is_active: raise HTTPException(403, "Account suspended")
    return {"access_token": make_token(u.id, u.role), "token_type":"bearer", "user": su(u)}

@app.get("/auth/me", tags=["Auth"])
async def me(u: User = Depends(current_user)): return su(u)

@app.put("/auth/me", tags=["Auth"])
async def update_me(
    full_name: Optional[str]=Form(None), bio: Optional[str]=Form(None),
    country: Optional[str]=Form(None), linkedin_url: Optional[str]=Form(None),
    website: Optional[str]=Form(None), avatar: Optional[UploadFile]=File(None),
    u: User = Depends(current_user), db: Session = Depends(get_db)
):
    if full_name:    u.full_name    = full_name
    if bio:          u.bio          = bio
    if country:      u.country      = country
    if linkedin_url: u.linkedin_url = linkedin_url
    if website:      u.website      = website
    if avatar:
        ext = Path(avatar.filename).suffix
        fn  = f"avatar_{u.id}{ext}"
        with open(UPLOAD_DIR/fn,"wb") as f: f.write(await avatar.read())
        u.avatar_url = f"/uploads/{fn}"
    db.commit(); db.refresh(u); return su(u)

# --- STARTUPS ---
@app.get("/startups", tags=["Startups"])
async def list_startups(query:str="", category:str="", stage:str="", country:str="",
                        sort_by:str="match_score", page:int=1, per_page:int=12,
                        db: Session = Depends(get_db)):
    q = db.query(Startup).filter(Startup.is_active==True)
    if query:    q = q.filter(Startup.name.ilike(f"%{query}%")|Startup.description.ilike(f"%{query}%"))
    if category: q = q.filter(Startup.category.ilike(f"%{category}%"))
    if stage:    q = q.filter(Startup.stage == stage)
    if country:  q = q.filter(Startup.country.ilike(f"%{country}%"))
    sm = {"match_score":Startup.match_score.desc(),"created_at":Startup.created_at.desc(),
          "funding_ask":Startup.funding_ask.desc(),"views":Startup.views.desc()}
    q  = q.order_by(sm.get(sort_by, Startup.match_score.desc()))
    total = q.count()
    rows  = q.offset((page-1)*per_page).limit(per_page).all()
    return {"total":total,"page":page,"per_page":per_page,
            "pages":(total+per_page-1)//per_page,"startups":[ss(s) for s in rows]}

@app.post("/startups", tags=["Startups"])
async def create_startup(payload: StartupCreate, u: User=Depends(current_user), db: Session=Depends(get_db)):
    import random
    s = Startup(owner_id=u.id, ai_score=round(random.uniform(65,95),1),
                match_score=round(random.uniform(70,99),1), **payload.dict())
    db.add(s); db.commit(); db.refresh(s); return ss(s)

@app.get("/startups/{sid}", tags=["Startups"])
async def get_startup(sid:int, db: Session=Depends(get_db)):
    s = db.query(Startup).filter(Startup.id==sid, Startup.is_active==True).first()
    if not s: raise HTTPException(404,"Not found")
    s.views += 1; db.commit(); return ss(s)

@app.put("/startups/{sid}", tags=["Startups"])
async def update_startup(sid:int, payload: StartupUpdate, u:User=Depends(current_user), db:Session=Depends(get_db)):
    s = db.query(Startup).filter(Startup.id==sid).first()
    if not s: raise HTTPException(404,"Not found")
    if s.owner_id != u.id: raise HTTPException(403,"Not your startup")
    for k,v in payload.dict(exclude_none=True).items(): setattr(s,k,v)
    s.updated_at = datetime.utcnow(); db.commit(); db.refresh(s); return ss(s)

@app.delete("/startups/{sid}", tags=["Startups"])
async def delete_startup(sid:int, u:User=Depends(current_user), db:Session=Depends(get_db)):
    s = db.query(Startup).filter(Startup.id==sid).first()
    if not s or s.owner_id != u.id: raise HTTPException(403,"Not authorized")
    s.is_active = False; db.commit(); return {"message":"Removed"}

@app.post("/startups/{sid}/logo", tags=["Startups"])
async def upload_logo(sid:int, logo:UploadFile=File(...), u:User=Depends(current_user), db:Session=Depends(get_db)):
    s = db.query(Startup).filter(Startup.id==sid).first()
    if not s or s.owner_id!=u.id: raise HTTPException(403,"Not authorized")
    fn = f"logo_{sid}{Path(logo.filename).suffix}"
    with open(UPLOAD_DIR/fn,"wb") as f: f.write(await logo.read())
    s.logo_url = f"/uploads/{fn}"; db.commit(); return {"logo_url":s.logo_url}

# --- INVESTORS ---
@app.post("/investors/profile", tags=["Investors"])
async def upsert_investor(payload: InvestorProfileCreate, u:User=Depends(current_user), db:Session=Depends(get_db)):
    p = db.query(InvestorProfile).filter(InvestorProfile.user_id==u.id).first()
    if p:
        for k,v in payload.dict().items(): setattr(p,k,v)
        db.commit(); db.refresh(p); return si(p)
    p = InvestorProfile(user_id=u.id, **payload.dict())
    db.add(p); db.commit(); db.refresh(p); return si(p)

@app.get("/investors", tags=["Investors"])
async def list_investors(page:int=1, per_page:int=12, db:Session=Depends(get_db)):
    q = db.query(InvestorProfile)
    total = q.count(); rows = q.offset((page-1)*per_page).limit(per_page).all()
    return {"total":total,"page":page,"investors":[si(p) for p in rows]}

@app.get("/investors/match/{startup_id}", tags=["Investors"])
async def match_investors(startup_id:int, limit:int=20, u:User=Depends(current_user), db:Session=Depends(get_db)):
    s = db.query(Startup).filter(Startup.id==startup_id).first()
    if not s: raise HTTPException(404,"Not found")
    investors = db.query(InvestorProfile).all()
    matches   = [{**si(p), "match_score": compute_match(s,p)} for p in investors]
    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return {"startup_id":startup_id,"matches":matches[:limit]}

# --- AI ---
@app.post("/ai/chat", tags=["AI"])
async def chat_endpoint(payload: ChatMsg, u=Depends(optional_user)):
    r = await ai_chat(payload.message, payload.context or {})
    return {"response":r,"timestamp":datetime.utcnow().isoformat(),
            "model":"gpt-4o-mini" if OPENAI_KEY else "rule-based"}

@app.post("/ai/analyze-pitch", tags=["AI"])
async def analyze_pitch(file:UploadFile=File(...), startup_id:Optional[int]=Form(None),
                        u:User=Depends(current_user), db:Session=Depends(get_db)):
    if Path(file.filename).suffix.lower() not in {".pdf",".pptx",".ppt"}:
        raise HTTPException(400,"Only PDF/PPTX accepted")
    fn = f"pitch_{u.id}_{int(time.time())}{Path(file.filename).suffix}"
    content = await file.read()
    with open(UPLOAD_DIR/fn,"wb") as f: f.write(content)
    r = await analyze_pitch_ai(content)
    rec = PitchAnalysis(user_id=u.id, startup_id=startup_id, file_name=file.filename,
        file_path=str(UPLOAD_DIR/fn), overall_score=r["scores"]["overall"],
        market_score=r["scores"]["market"], team_score=r["scores"]["team"],
        product_score=r["scores"]["product"], financials_score=r["scores"]["financials"],
        competitive_score=r["scores"]["competitive"], traction_score=r["scores"]["traction"],
        ai_feedback=r["feedback"], matched_investors=r["investor_matches"])
    db.add(rec); db.commit()
    return {"analysis_id":rec.id,"file_name":file.filename,**r}

@app.get("/ai/analyses", tags=["AI"])
async def my_analyses(u:User=Depends(current_user), db:Session=Depends(get_db)):
    return db.query(PitchAnalysis).filter(PitchAnalysis.user_id==u.id).order_by(PitchAnalysis.created_at.desc()).all()

@app.post("/ai/generate-outreach", tags=["AI"])
async def gen_outreach(startup_id:int, investor_id:int, u:User=Depends(current_user), db:Session=Depends(get_db)):
    s   = db.query(Startup).filter(Startup.id==startup_id).first()
    inv = db.query(InvestorProfile).filter(InvestorProfile.id==investor_id).first()
    if not s or not inv: raise HTTPException(404,"Not found")
    prompt = f"Write a cold outreach email from founder of '{s.name}' ({s.category}, {s.stage}) to {inv.user.full_name} at {inv.firm_name}. Under 150 words. Include subject line."
    email  = await ai_chat(prompt)
    return {"email_draft":email,"startup":s.name,"investor":inv.user.full_name}

# --- NETWORK ---
@app.post("/connections", tags=["Network"])
async def send_conn(payload: ConnReq, u:User=Depends(current_user), db:Session=Depends(get_db)):
    if payload.receiver_id == u.id: raise HTTPException(400,"Cannot connect with yourself")
    if db.query(Connection).filter(Connection.requester_id==u.id,Connection.receiver_id==payload.receiver_id).first():
        raise HTTPException(400,"Already sent")
    c = Connection(requester_id=u.id, receiver_id=payload.receiver_id, message=payload.message)
    db.add(c); db.commit(); db.refresh(c); return {"message":"Sent","id":c.id}

@app.get("/connections", tags=["Network"])
async def get_conns(u:User=Depends(current_user), db:Session=Depends(get_db)):
    sent = db.query(Connection).filter(Connection.requester_id==u.id).all()
    recv = db.query(Connection).filter(Connection.receiver_id==u.id).all()
    return {"sent":len(sent),"received":len(recv),
            "accepted":len([c for c in sent+recv if c.status=="accepted"]),
            "pending":len([c for c in recv if c.status=="pending"]),
            "connections":[sc(c) for c in sent+recv]}

@app.put("/connections/{cid}/respond", tags=["Network"])
async def respond_conn(cid:int, accept:bool, u:User=Depends(current_user), db:Session=Depends(get_db)):
    c = db.query(Connection).filter(Connection.id==cid, Connection.receiver_id==u.id).first()
    if not c: raise HTTPException(404,"Not found")
    c.status = "accepted" if accept else "rejected"; c.updated_at = datetime.utcnow()
    db.commit(); return {"message":f"Connection {'accepted' if accept else 'rejected'}"}

@app.post("/bookmarks/{startup_id}", tags=["Network"])
async def toggle_bookmark(startup_id:int, u:User=Depends(current_user), db:Session=Depends(get_db)):
    b = db.query(Bookmark).filter(Bookmark.user_id==u.id, Bookmark.startup_id==startup_id).first()
    if b: db.delete(b); db.commit(); return {"bookmarked":False}
    db.add(Bookmark(user_id=u.id, startup_id=startup_id)); db.commit(); return {"bookmarked":True}

@app.get("/bookmarks", tags=["Network"])
async def get_bookmarks(u:User=Depends(current_user), db:Session=Depends(get_db)):
    bms = db.query(Bookmark).filter(Bookmark.user_id==u.id).all()
    startups = [db.query(Startup).filter(Startup.id==b.startup_id).first() for b in bms]
    return {"bookmarks":[ss(s) for s in startups if s]}

@app.post("/messages", tags=["Network"])
async def send_msg(payload: MsgCreate, u:User=Depends(current_user), db:Session=Depends(get_db)):
    m = Message(sender_id=u.id, receiver_id=payload.receiver_id, content=payload.content)
    db.add(m); db.commit(); db.refresh(m); return {"message":"Sent","id":m.id}

@app.get("/messages/{uid}", tags=["Network"])
async def get_convo(uid:int, u:User=Depends(current_user), db:Session=Depends(get_db)):
    msgs = db.query(Message).filter(
        ((Message.sender_id==u.id)&(Message.receiver_id==uid))|
        ((Message.sender_id==uid)&(Message.receiver_id==u.id))
    ).order_by(Message.created_at).all()
    for m in msgs:
        if m.receiver_id==u.id and not m.is_read: m.is_read=True
    db.commit(); return {"messages":[sm(m) for m in msgs]}

# --- EVENTS ---
@app.get("/events", tags=["Events"])
async def list_events(event_type:str="", page:int=1, per_page:int=12, db:Session=Depends(get_db)):
    q = db.query(Event).filter(Event.event_date >= datetime.utcnow())
    if event_type: q = q.filter(Event.event_type==event_type)
    total = q.count(); rows = q.order_by(Event.event_date).offset((page-1)*per_page).limit(per_page).all()
    return {"total":total,"events":[se(e) for e in rows]}

@app.post("/events", tags=["Events"])
async def create_event(title:str=Form(...), description:str=Form(""), event_type:str=Form("Networking"),
                       location:str=Form(""), is_virtual:bool=Form(True), event_date:str=Form(...),
                       max_attendees:int=Form(100), u:User=Depends(current_user), db:Session=Depends(get_db)):
    e = Event(organizer_id=u.id, title=title, description=description, event_type=event_type,
              location=location, is_virtual=is_virtual, event_date=datetime.fromisoformat(event_date),
              max_attendees=max_attendees)
    db.add(e); db.commit(); db.refresh(e); return se(e)

# --- ANALYTICS ---
@app.get("/analytics/overview", tags=["Analytics"])
async def analytics(db:Session=Depends(get_db)):
    return {"platform":{"total_startups":db.query(Startup).filter(Startup.is_active==True).count(),
                        "total_investors":db.query(InvestorProfile).count(),
                        "total_users":db.query(User).filter(User.is_active==True).count(),
                        "connections":db.query(Connection).filter(Connection.status=="accepted").count(),
                        "pitches_analyzed":db.query(PitchAnalysis).count()},
            "funding":{"total_deployed":2_400_000_000,"avg_match_score":91.4,"active_deals":1847}}

@app.get("/analytics/funding-trends", tags=["Analytics"])
async def funding_trends():
    return {"monthly":[120,95,145,180,210,165,240,195,260,310,285,340],
            "months":["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
            "sectors":{"AI/ML":28,"FinTech":22,"HealthTech":18,"CleanTech":15,"Other":17}}

@app.get("/analytics/leaderboard", tags=["Analytics"])
async def leaderboard(db:Session=Depends(get_db)):
    top = db.query(Startup).filter(Startup.is_active==True).order_by(Startup.match_score.desc()).limit(10).all()
    return {"top_startups":[ss(s) for s in top]}

# ──────────────────────────────────────────────────────────────
#  SEED DEMO DATA INTO MYSQL
# ──────────────────────────────────────────────────────────────
def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() > 0: return
        print("🌱 Seeding demo data into MySQL...")

        users = [
            User(email="founder@demo.com",  full_name="Arjun Mehta", role="founder",  country="India",     password_hash=hash_pw("demo1234")),
            User(email="investor@demo.com", full_name="Vikram Nair", role="investor", country="USA",       password_hash=hash_pw("demo1234")),
            User(email="sarah@a16z.com",    full_name="Sarah Chen",  role="investor", country="USA",       password_hash=hash_pw("demo1234")),
            User(email="amir@500.co",       full_name="Amir Hassan", role="investor", country="UAE",       password_hash=hash_pw("demo1234")),
        ]
        for u in users: db.add(u)
        db.flush()

        profiles = [
            InvestorProfile(user_id=users[1].id, firm_name="Sequoia India",       title="General Partner",   aum="$2.1B", check_size_min=500000,  check_size_max=10000000, investment_focus=["FinTech","AI/ML","SaaS"],  preferred_stages=["Seed","Series A"],     preferred_regions=["India","SEA"],   portfolio_count=47, deals_per_year=12, is_verified=True),
            InvestorProfile(user_id=users[2].id, firm_name="Andreessen Horowitz", title="Managing Director", aum="$4.8B", check_size_min=1000000, check_size_max=50000000, investment_focus=["DeepTech","HealthTech"],  preferred_stages=["Series A","Series B"], preferred_regions=["USA","Global"],  portfolio_count=63, deals_per_year=21, is_verified=True),
            InvestorProfile(user_id=users[3].id, firm_name="500 Startups MENA",   title="Founding Partner",  aum="$800M", check_size_min=100000,  check_size_max=3000000,  investment_focus=["AgriTech","FinTech"],     preferred_stages=["Pre-Seed","Seed"],     preferred_regions=["MENA","Africa"], portfolio_count=38, deals_per_year=8,  is_verified=True),
        ]
        for p in profiles: db.add(p)

        startups = [
            Startup(owner_id=users[0].id, name="SolarGrid AI",  category="CleanTech",  stage="Series A", country="India",     funding_ask=2400000, equity_offered=12, current_arr=800000,  team_size=18, founded_year=2022, tags=["CleanTech","AI/ML"],  ai_score=89.5, match_score=97.2, is_featured=True,  tagline="AI-optimized solar microgrids"),
            Startup(owner_id=users[0].id, name="NanoMed Dx",    category="HealthTech", stage="Seed",     country="Kenya",     funding_ask=1800000, equity_offered=15, current_arr=120000,  team_size=9,  founded_year=2023, tags=["HealthTech","DeepTech"],ai_score=92.1, match_score=94.0, is_featured=True,  tagline="Lab diagnostics from smartphone"),
            Startup(owner_id=users[0].id, name="EduVerse AI",   category="EdTech",     stage="Pre-Seed", country="Brazil",    funding_ask=750000,  equity_offered=18, current_arr=0,       team_size=5,  founded_year=2024, tags=["EdTech","AI/ML"],      ai_score=78.4, match_score=88.0, is_featured=False, tagline="Adaptive AI tutor for K-12"),
            Startup(owner_id=users[0].id, name="PayBridge",     category="FinTech",    stage="Seed",     country="Singapore", funding_ask=3200000, equity_offered=10, current_arr=450000,  team_size=12, founded_year=2023, tags=["FinTech","Blockchain"], ai_score=85.2, match_score=91.0, is_featured=True,  tagline="Cross-border B2B payments ASEAN"),
            Startup(owner_id=users[0].id, name="AgriBot India", category="AgriTech",   stage="Pre-Seed", country="India",     funding_ask=500000,  equity_offered=20, current_arr=0,       team_size=4,  founded_year=2024, tags=["AgriTech","AI/ML"],    ai_score=74.8, match_score=85.0, is_featured=False, tagline="AI drones for precision farming"),
            Startup(owner_id=users[0].id, name="HealthSync",    category="HealthTech", stage="Series A", country="USA",       funding_ask=5200000, equity_offered=8,  current_arr=2100000, team_size=34, founded_year=2021, tags=["HealthTech","SaaS"],   ai_score=93.6, match_score=96.0, is_featured=True,  tagline="Remote patient monitoring AI"),
        ]
        for s in startups: db.add(s)

        events = [
            Event(organizer_id=users[1].id, title="Global Startup Championship 2025", event_type="Pitch Competition", location="San Francisco + Virtual", is_virtual=True,  event_date=datetime(2025,6,15), max_attendees=2400),
            Event(organizer_id=users[2].id, title="AI Venture Summit 2025",           event_type="Summit",            location="Singapore",              is_virtual=False, event_date=datetime(2025,7,8),  max_attendees=5000),
            Event(organizer_id=users[3].id, title="Africa Tech Demo Day",             event_type="Demo Day",          location="Nairobi + Virtual",      is_virtual=True,  event_date=datetime(2025,6,3),  max_attendees=800),
        ]
        for e in events: db.add(e)

        db.commit()
        print("✅ MySQL seeded! Demo accounts:")
        print("   founder@demo.com  / demo1234")
        print("   investor@demo.com / demo1234")

    except Exception as ex:
        print(f"⚠️  Seed skipped (may already exist): {ex}")
        db.rollback()
    finally:
        db.close()

# ──────────────────────────────────────────────────────────────
#  STARTUP EVENT
# ──────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    seed()
    print("\n" + "═"*55)
    print("  🚀  VentureAI — Running!")
    print("═"*55)
    print("  🌐  http://localhost:8000        (Website)")
    print("  📡  http://localhost:8000/docs   (API Docs)")
    print(f"  🗄️   MySQL → {MYSQL_DB}")
    print(f"  🤖  AI: {'OpenAI GPT-4' if OPENAI_KEY else 'Rule-based (set OPENAI_API_KEY)'}")
    print("═"*55 + "\n")

# ──────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)
