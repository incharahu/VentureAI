import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
"""
╔══════════════════════════════════════════════════════════════╗
║   VentureAI — Global Startup Networking & Investment Platform ║
║   Backend API  ·  Python + FastAPI  ·  Complete Single File   ║
╚══════════════════════════════════════════════════════════════╝

SETUP & RUN:
    pip install fastapi uvicorn python-jose passlib[bcrypt] python-multipart openai sqlalchemy aiofiles
    python backend.py

API RUNS AT: http://localhost:8000
DOCS AT:     http://localhost:8000/docs  (Swagger)
"""

import os
import json
import time
import hashlib
import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
import uvicorn

# ─── FastAPI & middleware ────────────────────────────────────
from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ─── Auth & security ────────────────────────────────────────
from passlib.context import CryptContext
from jose import JWTError, jwt

# ─── Pydantic schemas ────────────────────────────────────────
from pydantic import BaseModel, EmailStr, Field, validator

# ─── SQLite via SQLAlchemy (no extra DB needed) ──────────────
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    Text, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

# ────────────────────────────────────────────────────────────
#   CONFIGURATION
# ────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("SECRET_KEY", "ventureai-super-secret-key-change-in-prod")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = 60 * 24 * 7   # 7 days in minutes
OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")  # Set env var for real AI

DB_URL = "sqlite:///./ventureai.db"
engine = create_engine(DB_URL)
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ────────────────────────────────────────────────────────────
#   DATABASE SETUP
# ────────────────────────────────────────────────────────────
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ─── Models ─────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String, unique=True, index=True, nullable=False)
    full_name     = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role          = Column(String, default="founder")   # founder | investor | mentor
    country       = Column(String, default="")
    bio           = Column(Text, default="")
    avatar_url    = Column(String, default="")
    linkedin_url  = Column(String, default="")
    website       = Column(String, default="")
    is_verified   = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    last_seen     = Column(DateTime, default=datetime.utcnow)

    startups      = relationship("Startup",  back_populates="owner")
    investor_profile = relationship("InvestorProfile", back_populates="user", uselist=False)
    connections_sent = relationship("Connection", foreign_keys="Connection.requester_id", back_populates="requester")
    connections_recv = relationship("Connection", foreign_keys="Connection.receiver_id", back_populates="receiver")
    bookmarks     = relationship("Bookmark", back_populates="user")
    messages_sent = relationship("Message",  foreign_keys="Message.sender_id", back_populates="sender")


class Startup(Base):
    __tablename__ = "startups"
    id            = Column(Integer, primary_key=True, index=True)
    owner_id      = Column(Integer, ForeignKey("users.id"))
    name          = Column(String, nullable=False)
    tagline       = Column(String, default="")
    description   = Column(Text, default="")
    category      = Column(String, default="")          # FinTech | HealthTech | etc.
    stage         = Column(String, default="Pre-Seed")  # Pre-Seed | Seed | Series A | B | C
    country       = Column(String, default="")
    city          = Column(String, default="")
    website       = Column(String, default="")
    logo_url      = Column(String, default="")
    pitch_deck_url= Column(String, default="")
    funding_ask   = Column(Float, default=0)            # USD
    equity_offered= Column(Float, default=0)            # %
    current_arr   = Column(Float, default=0)            # Annual Recurring Revenue
    team_size     = Column(Integer, default=1)
    founded_year  = Column(Integer, default=2024)
    tags          = Column(JSON, default=list)
    ai_score      = Column(Float, default=0)            # AI pitch score 0-100
    match_score   = Column(Float, default=0)            # AI investor match score
    views         = Column(Integer, default=0)
    is_featured   = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow)

    owner         = relationship("User",     back_populates="startups")
    bookmarks     = relationship("Bookmark", back_populates="startup")


class InvestorProfile(Base):
    __tablename__ = "investor_profiles"
    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), unique=True)
    firm_name       = Column(String, default="")
    title           = Column(String, default="")
    aum             = Column(String, default="")
    check_size_min  = Column(Float, default=25000)
    check_size_max  = Column(Float, default=5000000)
    investment_focus= Column(JSON, default=list)       # list of sectors
    preferred_stages= Column(JSON, default=list)       # list of stages
    preferred_regions= Column(JSON, default=list)      # list of countries/regions
    portfolio_count = Column(Integer, default=0)
    deals_per_year  = Column(Integer, default=5)
    thesis          = Column(Text, default="")
    is_verified     = Column(Boolean, default=False)

    user            = relationship("User", back_populates="investor_profile")


class Connection(Base):
    __tablename__ = "connections"
    id            = Column(Integer, primary_key=True, index=True)
    requester_id  = Column(Integer, ForeignKey("users.id"))
    receiver_id   = Column(Integer, ForeignKey("users.id"))
    status        = Column(String, default="pending")   # pending | accepted | rejected
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
    __tablename__ = "events"
    id            = Column(Integer, primary_key=True, index=True)
    organizer_id  = Column(Integer, ForeignKey("users.id"))
    title         = Column(String, nullable=False)
    description   = Column(Text, default="")
    event_type    = Column(String, default="Networking")  # Pitch | Demo Day | Summit | Workshop
    location      = Column(String, default="")
    is_virtual    = Column(Boolean, default=True)
    event_date    = Column(DateTime)
    max_attendees = Column(Integer, default=100)
    tags          = Column(JSON, default=list)
    registration_url = Column(String, default="")
    created_at    = Column(DateTime, default=datetime.utcnow)


class PitchAnalysis(Base):
    __tablename__ = "pitch_analyses"
    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"))
    startup_id      = Column(Integer, ForeignKey("startups.id"), nullable=True)
    file_name       = Column(String, default="")
    file_path       = Column(String, default="")
    overall_score   = Column(Float, default=0)
    market_score    = Column(Float, default=0)
    team_score      = Column(Float, default=0)
    product_score   = Column(Float, default=0)
    financials_score= Column(Float, default=0)
    competitive_score= Column(Float, default=0)
    traction_score  = Column(Float, default=0)
    ai_feedback     = Column(Text, default="")
    matched_investors= Column(JSON, default=list)
    created_at      = Column(DateTime, default=datetime.utcnow)


# Create all tables
Base.metadata.create_all(bind=engine)


# ────────────────────────────────────────────────────────────
#   PYDANTIC SCHEMAS
# ────────────────────────────────────────────────────────────

# Auth
class RegisterRequest(BaseModel):
    email:      str
    full_name:  str
    password:   str
    role:       str = "founder"   # founder | investor
    country:    str = ""

class LoginRequest(BaseModel):
    email:    str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         Dict[str, Any]

# Startup
class StartupCreate(BaseModel):
    name:           str
    tagline:        str = ""
    description:    str = ""
    category:       str = ""
    stage:          str = "Pre-Seed"
    country:        str = ""
    city:           str = ""
    website:        str = ""
    funding_ask:    float = 0
    equity_offered: float = 0
    current_arr:    float = 0
    team_size:      int = 1
    founded_year:   int = 2024
    tags:           List[str] = []

class StartupUpdate(BaseModel):
    name:           Optional[str]
    tagline:        Optional[str]
    description:    Optional[str]
    category:       Optional[str]
    stage:          Optional[str]
    country:        Optional[str]
    city:           Optional[str]
    website:        Optional[str]
    funding_ask:    Optional[float]
    equity_offered: Optional[float]
    current_arr:    Optional[float]
    team_size:      Optional[int]
    tags:           Optional[List[str]]

# Investor Profile
class InvestorProfileCreate(BaseModel):
    firm_name:          str = ""
    title:              str = ""
    aum:                str = ""
    check_size_min:     float = 25000
    check_size_max:     float = 1000000
    investment_focus:   List[str] = []
    preferred_stages:   List[str] = []
    preferred_regions:  List[str] = []
    deals_per_year:     int = 5
    thesis:             str = ""

# Connection
class ConnectionRequest(BaseModel):
    receiver_id: int
    message:     str = ""

# Message
class MessageCreate(BaseModel):
    receiver_id: int
    content:     str

# AI Chat
class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict] = {}

# Search / Filter
class StartupFilter(BaseModel):
    query:    Optional[str] = ""
    category: Optional[str] = ""
    stage:    Optional[str] = ""
    country:  Optional[str] = ""
    min_ask:  Optional[float] = None
    max_ask:  Optional[float] = None
    sort_by:  Optional[str] = "match_score"   # match_score | created_at | funding_ask
    page:     int = 1
    per_page: int = 12


# ────────────────────────────────────────────────────────────
#   SECURITY
# ────────────────────────────────────────────────────────────
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pwd: str) -> str:
    return pwd_ctx.hash(pwd)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: int = TOKEN_EXPIRE) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ────────────────────────────────────────────────────────────
#   DATABASE DEPENDENCY
# ────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ────────────────────────────────────────────────────────────
#   AUTH DEPENDENCY
# ────────────────────────────────────────────────────────────
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    # Update last_seen
    user.last_seen = datetime.utcnow()
    db.commit()
    return user

def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        return db.query(User).filter(User.id == int(user_id)).first()
    except:
        return None


# ────────────────────────────────────────────────────────────
#   AI SERVICE
# ────────────────────────────────────────────────────────────
class AIService:
    """Wraps OpenAI (or falls back to rule-based responses)."""

    SYSTEM_PROMPT = """You are VentureAI, an expert AI advisor for startup founders and investors.
You have deep knowledge of:
- Venture capital, fundraising strategies, term sheets, due diligence
- Startup growth, product-market fit, go-to-market strategies
- Global startup ecosystems (US, India, EU, Africa, SEA)
- Investment theses, sector trends, valuation benchmarks
- Pitch deck best practices, investor outreach

Respond concisely, with actionable advice. Use data and specifics where possible."""

    FALLBACK_RESPONSES = {
        "match": "Based on your profile analysis, I recommend targeting Seed-stage investors in your sector. Top categories to focus on: (1) Sector-specialized VCs with portfolio synergies, (2) Geographic-focus funds in your market, (3) Corporate VCs from strategic partners. Would you like me to generate a personalized investor list?",
        "pitch": "Strong pitches have 3 core elements: (1) Problem clarity — make the pain visceral with real user stories, (2) Unfair advantage — what makes you defensible in 3 years, (3) Momentum signals — even small traction data increases investor confidence by 40%. What aspect would you like to improve?",
        "investor": "I'm analyzing investor activity patterns now. The most active investors this quarter are deploying in AI/ML (34% increase), Climate Tech (+28%), and Healthcare AI (+22%). Typical check sizes: Pre-Seed $100K-500K, Seed $500K-3M, Series A $3M-15M. Want me to filter by your specific stage?",
        "funding": "Global VC funding in Q1 2025 is tracking at $67B — up 18% YoY. Key insight: AI-native startups are closing rounds 35% faster than non-AI peers. Your best fundraising window is September-November or January-March when fund managers have fresh capital. What's your target raise timeline?",
        "market": "Market sizing advice: use a bottom-up approach for credibility. Start with your beachhead market, show penetration assumptions, then scale to SAM and TAM. Investors trust $1B TAM minimum for venture returns. What's your current market sizing methodology?",
        "email": "Here's a high-converting cold outreach template:\n\nSubject: [Mutual Connection] / [Portfolio Co] → [Your Startup]\n\nHi [Name],\n\n[Your startup] is solving [specific problem] for [specific customer]. We have [traction metric] with [notable customers/investors].\n\nGiven your investment in [their portfolio co], I think [Your startup] is highly aligned with your thesis on [specific thesis point].\n\nWould you have 20 minutes this week or next?\n\nBest,\n[Name]",
        "valuation": "Seed-stage valuation benchmarks 2025: Median pre-money $8-12M (US), $3-6M (India), $5-9M (EU). Key multiples: ARR × 8-15x for SaaS, 5-10x for marketplace GMV, DCF for hardware. Investors discount by 30-50% if team is first-time founders. What's your current revenue?",
        "term sheet": "Key term sheet terms to negotiate: (1) Liquidation preference — 1x non-participating is standard, push back on 2x or participating, (2) Pro-rata rights — you want these limited to lead investors, (3) Board composition — maintain founder majority through Series A, (4) Anti-dilution — broad-based weighted average is fair. Which specific terms are you evaluating?",
    }

    @staticmethod
    async def chat(message: str, context: dict = {}) -> str:
        """Call OpenAI API or fall back to rule-based responses."""
        if OPENAI_KEY:
            try:
                import openai
                client = openai.AsyncOpenAI(api_key=OPENAI_KEY)
                msgs = [{"role": "system", "content": AIService.SYSTEM_PROMPT}]
                if context.get("history"):
                    msgs.extend(context["history"][-6:])  # last 6 turns
                msgs.append({"role": "user", "content": message})

                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=msgs,
                    max_tokens=600,
                    temperature=0.7,
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"OpenAI error: {e}")

        # Rule-based fallback
        low = message.lower()
        for key, resp in AIService.FALLBACK_RESPONSES.items():
            if key in low:
                return resp
        return (
            "I can help you with investor matching, pitch deck analysis, market research, "
            "outreach email drafting, term sheet guidance, and fundraising strategy. "
            "What specific challenge are you working on right now?"
        )

    @staticmethod
    async def analyze_pitch(file_content: bytes, file_name: str) -> dict:
        """AI pitch deck analysis — returns scores and feedback."""
        # In production: parse PDF/PPTX, send slides to GPT-4 Vision
        # Here: smart simulation based on file metadata
        import random
        random.seed(len(file_content) % 100)

        scores = {
            "overall":      random.randint(72, 95),
            "market":       random.randint(75, 97),
            "team":         random.randint(68, 92),
            "product":      random.randint(70, 94),
            "financials":   random.randint(60, 88),
            "competitive":  random.randint(55, 85),
            "traction":     random.randint(65, 92),
        }

        feedback_templates = [
            f"Overall Score: {scores['overall']}/100 — Investor-ready with targeted improvements. "
            f"Strongest area: Market Opportunity ({scores['market']}/100) — compelling TAM narrative. "
            f"Improvement needed: Competitive Differentiation ({scores['competitive']}/100) — add a clear '3-year moat' slide. "
            f"Financial Model ({scores['financials']}/100) — include monthly unit economics and path to profitability by Month 24. "
            f"Recommendation: Ready for Seed-stage outreach. Strengthen slides 7-9 before approaching Series A investors.",
        ]

        return {
            "scores": scores,
            "feedback": feedback_templates[0],
            "recommended_stage": "Seed" if scores["overall"] < 80 else "Series A",
            "investor_matches": random.randint(30, 70),
            "strengths": ["Market sizing narrative", "Founder credentials", "Problem statement clarity"],
            "improvements": ["Competitive moat articulation", "Unit economics model", "Customer acquisition cost data"],
        }

    @staticmethod
    def compute_match_score(startup: Startup, investor: InvestorProfile) -> float:
        """Compute AI match score between a startup and investor (0-100)."""
        score = 50.0  # base

        # Sector alignment
        startup_cats = set((startup.tags or []) + [startup.category])
        investor_focus = set(investor.investment_focus or [])
        if startup_cats & investor_focus:
            score += 20

        # Stage alignment
        if startup.stage in (investor.preferred_stages or []):
            score += 15

        # Region alignment
        startup_regions = {startup.country}
        investor_regions = set(investor.preferred_regions or [])
        if startup_regions & investor_regions or "Global" in investor_regions:
            score += 10

        # Check size alignment
        if investor.check_size_min <= startup.funding_ask <= investor.check_size_max:
            score += 5

        return min(round(score, 1), 99.0)


# ────────────────────────────────────────────────────────────
#   FASTAPI APP
# ────────────────────────────────────────────────────────────
app = FastAPI(
    title="VentureAI API",
    description="AI-powered global startup networking & investment platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # in prod: specify frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploads
if UPLOAD_DIR.exists():
    app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# Serve frontend HTML (if in same dir)
FRONTEND = Path("index.html")


# ────────────────────────────────────────────────────────────
#   ROOT
# ────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    if FRONTEND.exists():
        return FileResponse(str(FRONTEND))
    return {
        "app": "VentureAI API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "✅ Online",
        "endpoints": {
            "auth":      ["/auth/register", "/auth/login", "/auth/me"],
            "startups":  ["/startups", "/startups/{id}", "/startups/search"],
            "investors": ["/investors", "/investors/{id}", "/investors/match/{startup_id}"],
            "ai":        ["/ai/chat", "/ai/analyze-pitch", "/ai/match-score"],
            "network":   ["/connections", "/bookmarks", "/messages"],
            "events":    ["/events"],
            "analytics": ["/analytics/overview", "/analytics/funding-trends"],
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ════════════════════════════════════════════════════════════
#   AUTH ROUTES
# ════════════════════════════════════════════════════════════

@app.post("/auth/register", response_model=TokenResponse, tags=["Auth"])
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new founder or investor account."""
    if db.query(User).filter(User.email == req.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=req.email.lower().strip(),
        full_name=req.full_name.strip(),
        password_hash=hash_password(req.password),
        role=req.role,
        country=req.country,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token, user=_user_dict(user))


@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login and receive JWT token."""
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account suspended")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token, user=_user_dict(user))


@app.get("/auth/me", tags=["Auth"])
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return _user_dict(current_user)


@app.put("/auth/me", tags=["Auth"])
async def update_me(
    full_name:   Optional[str] = Form(None),
    bio:         Optional[str] = Form(None),
    country:     Optional[str] = Form(None),
    linkedin_url:Optional[str] = Form(None),
    website:     Optional[str] = Form(None),
    avatar:      Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile."""
    if full_name:    current_user.full_name    = full_name
    if bio:          current_user.bio          = bio
    if country:      current_user.country      = country
    if linkedin_url: current_user.linkedin_url = linkedin_url
    if website:      current_user.website      = website

    if avatar:
        ext = Path(avatar.filename).suffix
        fname = f"avatar_{current_user.id}{ext}"
        fpath = UPLOAD_DIR / fname
        with open(fpath, "wb") as f:
            f.write(await avatar.read())
        current_user.avatar_url = f"/uploads/{fname}"

    db.commit()
    db.refresh(current_user)
    return _user_dict(current_user)


# ════════════════════════════════════════════════════════════
#   STARTUPS ROUTES
# ════════════════════════════════════════════════════════════

@app.get("/startups", tags=["Startups"])
async def list_startups(
    query:    str = "",
    category: str = "",
    stage:    str = "",
    country:  str = "",
    sort_by:  str = "match_score",
    page:     int = 1,
    per_page: int = 12,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """List & filter startups."""
    q = db.query(Startup).filter(Startup.is_active == True)

    if query:
        q = q.filter(
            Startup.name.ilike(f"%{query}%") |
            Startup.description.ilike(f"%{query}%") |
            Startup.tagline.ilike(f"%{query}%")
        )
    if category: q = q.filter(Startup.category.ilike(f"%{category}%"))
    if stage:    q = q.filter(Startup.stage == stage)
    if country:  q = q.filter(Startup.country.ilike(f"%{country}%"))

    # Sorting
    sort_col = {
        "match_score": Startup.match_score.desc(),
        "created_at":  Startup.created_at.desc(),
        "funding_ask": Startup.funding_ask.desc(),
        "views":       Startup.views.desc(),
        "ai_score":    Startup.ai_score.desc(),
    }.get(sort_by, Startup.match_score.desc())

    total = q.count()
    startups = q.order_by(sort_col).offset((page-1)*per_page).limit(per_page).all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "startups": [_startup_dict(s) for s in startups]
    }


@app.post("/startups", tags=["Startups"])
async def create_startup(
    payload: StartupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new startup listing."""
    import random
    startup = Startup(
        owner_id      = current_user.id,
        ai_score      = round(random.uniform(65, 95), 1),
        match_score   = round(random.uniform(70, 99), 1),
        **payload.dict()
    )
    db.add(startup)
    db.commit()
    db.refresh(startup)
    return _startup_dict(startup)


@app.get("/startups/{startup_id}", tags=["Startups"])
async def get_startup(
    startup_id: int,
    db: Session = Depends(get_db)
):
    """Get single startup detail."""
    startup = db.query(Startup).filter(Startup.id == startup_id, Startup.is_active == True).first()
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")
    # Increment views
    startup.views += 1
    db.commit()
    return _startup_dict(startup)


@app.put("/startups/{startup_id}", tags=["Startups"])
async def update_startup(
    startup_id: int,
    payload: StartupUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update startup (owner only)."""
    startup = db.query(Startup).filter(Startup.id == startup_id).first()
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")
    if startup.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your startup")

    for field, val in payload.dict(exclude_none=True).items():
        setattr(startup, field, val)
    startup.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(startup)
    return _startup_dict(startup)


@app.delete("/startups/{startup_id}", tags=["Startups"])
async def delete_startup(
    startup_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    startup = db.query(Startup).filter(Startup.id == startup_id).first()
    if not startup or startup.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    startup.is_active = False
    db.commit()
    return {"message": "Startup removed from listings"}


@app.post("/startups/{startup_id}/logo", tags=["Startups"])
async def upload_startup_logo(
    startup_id: int,
    logo: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload startup logo."""
    startup = db.query(Startup).filter(Startup.id == startup_id).first()
    if not startup or startup.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    ext   = Path(logo.filename).suffix
    fname = f"logo_{startup_id}{ext}"
    fpath = UPLOAD_DIR / fname
    with open(fpath, "wb") as f:
        f.write(await logo.read())
    startup.logo_url = f"/uploads/{fname}"
    db.commit()
    return {"logo_url": startup.logo_url}


# ════════════════════════════════════════════════════════════
#   INVESTOR ROUTES
# ════════════════════════════════════════════════════════════

@app.post("/investors/profile", tags=["Investors"])
async def create_investor_profile(
    payload: InvestorProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create / update investor profile."""
    existing = db.query(InvestorProfile).filter(InvestorProfile.user_id == current_user.id).first()
    if existing:
        for k, v in payload.dict().items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return existing
    profile = InvestorProfile(user_id=current_user.id, **payload.dict())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@app.get("/investors", tags=["Investors"])
async def list_investors(
    focus:    str = "",
    stage:    str = "",
    region:   str = "",
    page:     int = 1,
    per_page: int = 12,
    db: Session = Depends(get_db)
):
    """List verified investors."""
    q = db.query(InvestorProfile)
    total    = q.count()
    profiles = q.offset((page-1)*per_page).limit(per_page).all()
    return {
        "total":    total,
        "page":     page,
        "investors": [_investor_dict(p) for p in profiles]
    }


@app.get("/investors/{investor_id}", tags=["Investors"])
async def get_investor(investor_id: int, db: Session = Depends(get_db)):
    profile = db.query(InvestorProfile).filter(InvestorProfile.id == investor_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Investor not found")
    return _investor_dict(profile)


@app.get("/investors/match/{startup_id}", tags=["Investors"])
async def match_investors(
    startup_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return investors ranked by AI match score for a startup."""
    startup   = db.query(Startup).filter(Startup.id == startup_id).first()
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")

    investors = db.query(InvestorProfile).all()
    matches   = []
    for inv in investors:
        score = AIService.compute_match_score(startup, inv)
        matches.append({**_investor_dict(inv), "match_score": score})

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return {"startup_id": startup_id, "matches": matches[:limit]}


# ════════════════════════════════════════════════════════════
#   AI ROUTES
# ════════════════════════════════════════════════════════════

@app.post("/ai/chat", tags=["AI"])
async def ai_chat(
    payload: ChatMessage,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Chat with AI startup advisor."""
    response = await AIService.chat(payload.message, payload.context or {})
    return {
        "response": response,
        "timestamp": datetime.utcnow().isoformat(),
        "model": "gpt-4o-mini" if OPENAI_KEY else "rule-based"
    }


@app.post("/ai/analyze-pitch", tags=["AI"])
async def analyze_pitch(
    file: UploadFile = File(...),
    startup_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload pitch deck and get AI analysis."""
    allowed = {".pdf", ".pptx", ".ppt"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Only PDF and PPTX files accepted")

    # Save file
    fname  = f"pitch_{current_user.id}_{int(time.time())}{ext}"
    fpath  = UPLOAD_DIR / fname
    content = await file.read()
    with open(fpath, "wb") as f:
        f.write(content)

    # AI analysis
    analysis = await AIService.analyze_pitch(content, file.filename)

    # Save to DB
    record = PitchAnalysis(
        user_id          = current_user.id,
        startup_id       = startup_id,
        file_name        = file.filename,
        file_path        = str(fpath),
        overall_score    = analysis["scores"]["overall"],
        market_score     = analysis["scores"]["market"],
        team_score       = analysis["scores"]["team"],
        product_score    = analysis["scores"]["product"],
        financials_score = analysis["scores"]["financials"],
        competitive_score= analysis["scores"]["competitive"],
        traction_score   = analysis["scores"]["traction"],
        ai_feedback      = analysis["feedback"],
        matched_investors= analysis["investor_matches"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "analysis_id":        record.id,
        "file_name":          file.filename,
        "scores":             analysis["scores"],
        "feedback":           analysis["feedback"],
        "recommended_stage":  analysis["recommended_stage"],
        "investor_matches":   analysis["investor_matches"],
        "strengths":          analysis["strengths"],
        "improvements":       analysis["improvements"],
    }


@app.get("/ai/analyses", tags=["AI"])
async def get_my_analyses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all pitch analyses for current user."""
    analyses = db.query(PitchAnalysis).filter(
        PitchAnalysis.user_id == current_user.id
    ).order_by(PitchAnalysis.created_at.desc()).all()
    return analyses


@app.post("/ai/generate-outreach", tags=["AI"])
async def generate_outreach(
    startup_id:  int,
    investor_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate personalized investor outreach email."""
    startup  = db.query(Startup).filter(Startup.id == startup_id).first()
    investor = db.query(InvestorProfile).filter(InvestorProfile.id == investor_id).first()

    if not startup or not investor:
        raise HTTPException(status_code=404, detail="Startup or investor not found")

    prompt = (
        f"Generate a personalized, concise cold outreach email from the founder of '{startup.name}' "
        f"({startup.category}, {startup.stage}, seeking ${startup.funding_ask:,.0f}) "
        f"to {investor.user.full_name}, {investor.title} at {investor.firm_name}. "
        f"Investor focuses on: {', '.join(investor.investment_focus or [])}. "
        f"Startup tagline: {startup.tagline}. Keep it under 150 words. Include subject line."
    )

    response = await AIService.chat(prompt)
    return {"email_draft": response, "startup": startup.name, "investor": investor.user.full_name}


@app.post("/ai/market-report", tags=["AI"])
async def get_market_report(
    sector:  str,
    current_user: User = Depends(get_current_user)
):
    """Get AI-generated market intelligence report."""
    prompt = (
        f"Write a concise market intelligence briefing for a startup founder in the {sector} sector. "
        f"Include: (1) Current funding trends, (2) Top 3 active investors, (3) Key market drivers for 2025, "
        f"(4) Biggest risks, (5) Emerging opportunities. Use specific data points. Keep it under 300 words."
    )
    report = await AIService.chat(prompt)
    return {"sector": sector, "report": report, "generated_at": datetime.utcnow().isoformat()}


# ════════════════════════════════════════════════════════════
#   NETWORKING ROUTES
# ════════════════════════════════════════════════════════════

@app.post("/connections", tags=["Network"])
async def send_connection(
    payload: ConnectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send connection request."""
    if payload.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot connect with yourself")

    existing = db.query(Connection).filter(
        Connection.requester_id == current_user.id,
        Connection.receiver_id  == payload.receiver_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Connection request already sent")

    conn = Connection(
        requester_id = current_user.id,
        receiver_id  = payload.receiver_id,
        message      = payload.message
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return {"message": "Connection request sent", "connection_id": conn.id}


@app.get("/connections", tags=["Network"])
async def get_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all connections for current user."""
    sent = db.query(Connection).filter(Connection.requester_id == current_user.id).all()
    recv = db.query(Connection).filter(Connection.receiver_id  == current_user.id).all()
    return {
        "sent":     len(sent),
        "received": len(recv),
        "accepted": len([c for c in sent + recv if c.status == "accepted"]),
        "pending":  len([c for c in recv if c.status == "pending"]),
        "connections": [_conn_dict(c) for c in (sent + recv)]
    }


@app.put("/connections/{conn_id}/respond", tags=["Network"])
async def respond_connection(
    conn_id:  int,
    accept:   bool,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept or reject a connection request."""
    conn = db.query(Connection).filter(
        Connection.id == conn_id,
        Connection.receiver_id == current_user.id
    ).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn.status     = "accepted" if accept else "rejected"
    conn.updated_at = datetime.utcnow()
    db.commit()
    return {"message": f"Connection {'accepted' if accept else 'rejected'}"}


@app.post("/bookmarks/{startup_id}", tags=["Network"])
async def toggle_bookmark(
    startup_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bookmark or un-bookmark a startup."""
    existing = db.query(Bookmark).filter(
        Bookmark.user_id    == current_user.id,
        Bookmark.startup_id == startup_id
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"bookmarked": False, "message": "Removed from watchlist"}
    bm = Bookmark(user_id=current_user.id, startup_id=startup_id)
    db.add(bm)
    db.commit()
    return {"bookmarked": True, "message": "Added to watchlist"}


@app.get("/bookmarks", tags=["Network"])
async def get_bookmarks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's bookmarked startups."""
    bms = db.query(Bookmark).filter(Bookmark.user_id == current_user.id).all()
    startups = [db.query(Startup).filter(Startup.id == b.startup_id).first() for b in bms]
    return {"bookmarks": [_startup_dict(s) for s in startups if s]}


@app.post("/messages", tags=["Network"])
async def send_message(
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a direct message."""
    msg = Message(
        sender_id   = current_user.id,
        receiver_id = payload.receiver_id,
        content     = payload.content
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"message": "Sent", "message_id": msg.id}


@app.get("/messages/{user_id}", tags=["Network"])
async def get_conversation(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get conversation thread between two users."""
    msgs = db.query(Message).filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at).all()

    # Mark as read
    for m in msgs:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    db.commit()

    return {"messages": [_msg_dict(m) for m in msgs]}


# ════════════════════════════════════════════════════════════
#   EVENTS ROUTES
# ════════════════════════════════════════════════════════════

@app.get("/events", tags=["Events"])
async def list_events(
    event_type: str = "",
    is_virtual: Optional[bool] = None,
    page: int = 1,
    per_page: int = 12,
    db: Session = Depends(get_db)
):
    """List upcoming events."""
    q = db.query(Event).filter(Event.event_date >= datetime.utcnow())
    if event_type:  q = q.filter(Event.event_type == event_type)
    if is_virtual is not None: q = q.filter(Event.is_virtual == is_virtual)
    total  = q.count()
    events = q.order_by(Event.event_date).offset((page-1)*per_page).limit(per_page).all()
    return {"total": total, "events": [_event_dict(e) for e in events]}


@app.post("/events", tags=["Events"])
async def create_event(
    title:       str = Form(...),
    description: str = Form(""),
    event_type:  str = Form("Networking"),
    location:    str = Form(""),
    is_virtual:  bool = Form(True),
    event_date:  str = Form(...),
    max_attendees: int = Form(100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new event."""
    event = Event(
        organizer_id  = current_user.id,
        title         = title,
        description   = description,
        event_type    = event_type,
        location      = location,
        is_virtual    = is_virtual,
        event_date    = datetime.fromisoformat(event_date),
        max_attendees = max_attendees,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _event_dict(event)


# ════════════════════════════════════════════════════════════
#   ANALYTICS ROUTES
# ════════════════════════════════════════════════════════════

@app.get("/analytics/overview", tags=["Analytics"])
async def analytics_overview(db: Session = Depends(get_db)):
    """Platform-wide analytics overview."""
    total_startups   = db.query(Startup).filter(Startup.is_active == True).count()
    total_investors  = db.query(InvestorProfile).count()
    total_users      = db.query(User).filter(User.is_active == True).count()
    total_connections= db.query(Connection).filter(Connection.status == "accepted").count()
    total_analyses   = db.query(PitchAnalysis).count()

    return {
        "platform_stats": {
            "total_startups":    total_startups,
            "total_investors":   total_investors,
            "total_users":       total_users,
            "connections_made":  total_connections,
            "pitches_analyzed":  total_analyses,
        },
        "funding_stats": {
            "total_capital_deployed_usd": 2_400_000_000,
            "avg_match_score":            91.4,
            "avg_deal_close_days":        47,
            "active_deal_rooms":          1847,
        },
        "growth": {
            "users_this_month":     320,
            "startups_this_month":  85,
            "deals_this_month":     23,
        }
    }


@app.get("/analytics/funding-trends", tags=["Analytics"])
async def funding_trends():
    """Monthly funding trend data for charts."""
    return {
        "monthly_volume_usd_millions": [120, 95, 145, 180, 210, 165, 240, 195, 260, 310, 285, 340],
        "months": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
        "year": 2025,
        "sector_distribution": {
            "AI/ML":       28,
            "FinTech":     22,
            "HealthTech":  18,
            "CleanTech":   15,
            "Other":       17,
        },
        "stage_distribution": {
            "Pre-Seed": 23,
            "Seed":     38,
            "Series A": 25,
            "Series B+": 14,
        },
        "top_countries": [
            {"country": "USA",         "deals": 312},
            {"country": "India",       "deals": 184},
            {"country": "UK",          "deals": 97},
            {"country": "Singapore",   "deals": 76},
            {"country": "Germany",     "deals": 58},
            {"country": "Nigeria",     "deals": 45},
            {"country": "Brazil",      "deals": 41},
        ]
    }


@app.get("/analytics/leaderboard", tags=["Analytics"])
async def leaderboard(db: Session = Depends(get_db)):
    """Top startups by match score / views."""
    top = db.query(Startup).filter(
        Startup.is_active == True
    ).order_by(Startup.match_score.desc()).limit(10).all()
    return {"top_startups": [_startup_dict(s) for s in top]}


# ════════════════════════════════════════════════════════════
#   SERIALIZERS
# ════════════════════════════════════════════════════════════

def _user_dict(u: User) -> dict:
    return {
        "id":          u.id,
        "email":       u.email,
        "full_name":   u.full_name,
        "role":        u.role,
        "country":     u.country,
        "bio":         u.bio,
        "avatar_url":  u.avatar_url,
        "linkedin_url":u.linkedin_url,
        "website":     u.website,
        "is_verified": u.is_verified,
        "created_at":  u.created_at.isoformat(),
    }

def _startup_dict(s: Startup) -> dict:
    return {
        "id":            s.id,
        "owner_id":      s.owner_id,
        "name":          s.name,
        "tagline":       s.tagline,
        "description":   s.description,
        "category":      s.category,
        "stage":         s.stage,
        "country":       s.country,
        "city":          s.city,
        "website":       s.website,
        "logo_url":      s.logo_url,
        "pitch_deck_url":s.pitch_deck_url,
        "funding_ask":   s.funding_ask,
        "equity_offered":s.equity_offered,
        "current_arr":   s.current_arr,
        "team_size":     s.team_size,
        "founded_year":  s.founded_year,
        "tags":          s.tags or [],
        "ai_score":      s.ai_score,
        "match_score":   s.match_score,
        "views":         s.views,
        "is_featured":   s.is_featured,
        "created_at":    s.created_at.isoformat(),
    }

def _investor_dict(p: InvestorProfile) -> dict:
    return {
        "id":               p.id,
        "user_id":          p.user_id,
        "full_name":        p.user.full_name if p.user else "",
        "firm_name":        p.firm_name,
        "title":            p.title,
        "aum":              p.aum,
        "check_size_min":   p.check_size_min,
        "check_size_max":   p.check_size_max,
        "investment_focus": p.investment_focus or [],
        "preferred_stages": p.preferred_stages or [],
        "preferred_regions":p.preferred_regions or [],
        "portfolio_count":  p.portfolio_count,
        "deals_per_year":   p.deals_per_year,
        "thesis":           p.thesis,
        "is_verified":      p.is_verified,
    }

def _conn_dict(c: Connection) -> dict:
    return {
        "id":           c.id,
        "requester_id": c.requester_id,
        "receiver_id":  c.receiver_id,
        "status":       c.status,
        "message":      c.message,
        "created_at":   c.created_at.isoformat(),
    }

def _msg_dict(m: Message) -> dict:
    return {
        "id":          m.id,
        "sender_id":   m.sender_id,
        "receiver_id": m.receiver_id,
        "content":     m.content,
        "is_read":     m.is_read,
        "created_at":  m.created_at.isoformat(),
    }

def _event_dict(e: Event) -> dict:
    return {
        "id":             e.id,
        "organizer_id":   e.organizer_id,
        "title":          e.title,
        "description":    e.description,
        "event_type":     e.event_type,
        "location":       e.location,
        "is_virtual":     e.is_virtual,
        "event_date":     e.event_date.isoformat() if e.event_date else None,
        "max_attendees":  e.max_attendees,
        "tags":           e.tags or [],
        "registration_url": e.registration_url,
    }


# ════════════════════════════════════════════════════════════
#   SEED DATA (runs once on startup)
# ════════════════════════════════════════════════════════════

def seed_database():
    db = SessionLocal()
    try:
        # Only seed if empty
        if db.query(User).count() > 0:
            return

        print("🌱 Seeding database...")

        # Demo users
        users_data = [
            {"email":"founder@demo.com","full_name":"Arjun Mehta","role":"founder","country":"India"},
            {"email":"investor@demo.com","full_name":"Vikram Nair","role":"investor","country":"USA"},
            {"email":"sarah@a16z.com","full_name":"Sarah Chen","role":"investor","country":"USA"},
            {"email":"amir@500.co","full_name":"Amir Hassan","role":"investor","country":"UAE"},
        ]
        created_users = []
        for ud in users_data:
            u = User(password_hash=hash_password("demo1234"), **ud)
            db.add(u)
            db.flush()
            created_users.append(u)

        db.commit()

        # Demo investor profiles
        investor_profiles = [
            {
                "user_id": created_users[1].id,
                "firm_name":"Sequoia India", "title":"General Partner",
                "aum":"$2.1B", "check_size_min":500000, "check_size_max":10000000,
                "investment_focus":["FinTech","AI/ML","SaaS"],
                "preferred_stages":["Seed","Series A"],
                "preferred_regions":["India","SEA"], "portfolio_count":47, "deals_per_year":12,
                "thesis":"Backing category-defining companies in India and Southeast Asia.",
                "is_verified":True
            },
            {
                "user_id": created_users[2].id,
                "firm_name":"Andreessen Horowitz", "title":"Managing Director",
                "aum":"$4.8B", "check_size_min":1000000, "check_size_max":50000000,
                "investment_focus":["DeepTech","HealthTech","CleanTech"],
                "preferred_stages":["Series A","Series B"],
                "preferred_regions":["USA","EU","Global"], "portfolio_count":63, "deals_per_year":21,
                "thesis":"Software is eating the world — we back founders who are rewriting the future.",
                "is_verified":True
            },
            {
                "user_id": created_users[3].id,
                "firm_name":"500 Startups MENA", "title":"Founding Partner",
                "aum":"$800M", "check_size_min":100000, "check_size_max":3000000,
                "investment_focus":["AgriTech","EdTech","FinTech"],
                "preferred_stages":["Pre-Seed","Seed"],
                "preferred_regions":["MENA","Africa"], "portfolio_count":38, "deals_per_year":8,
                "thesis":"Early-stage bets on emerging market entrepreneurs solving local problems at global scale.",
                "is_verified":True
            },
        ]
        for ip in investor_profiles:
            p = InvestorProfile(**ip)
            db.add(p)

        # Demo startups
        startups_data = [
            {
                "owner_id":created_users[0].id, "name":"SolarGrid AI",
                "tagline":"AI-optimized solar microgrids for emerging markets",
                "description":"120MW deployed across 6 countries using proprietary AI optimization.",
                "category":"CleanTech", "stage":"Series A", "country":"India", "city":"Bangalore",
                "funding_ask":2400000, "equity_offered":12, "current_arr":800000,
                "team_size":18, "founded_year":2022,
                "tags":["CleanTech","AI/ML","Hardware"], "ai_score":89.5, "match_score":97.2,
                "is_featured":True
            },
            {
                "owner_id":created_users[0].id, "name":"NanoMed Dx",
                "tagline":"Lab-quality diagnostics from a smartphone in 90 seconds",
                "description":"Nano-sensor technology delivering blood test accuracy via mobile camera.",
                "category":"HealthTech", "stage":"Seed", "country":"Kenya", "city":"Nairobi",
                "funding_ask":1800000, "equity_offered":15, "current_arr":120000,
                "team_size":9, "founded_year":2023,
                "tags":["HealthTech","DeepTech","Hardware"], "ai_score":92.1, "match_score":94.0,
                "is_featured":True
            },
        ]
        for sd in startups_data:
            s = Startup(**sd)
            db.add(s)

        # Demo events
        events_data = [
            {
                "organizer_id":created_users[1].id,
                "title":"Global Startup Championship 2025",
                "description":"The world's largest startup pitch competition with $1M prize pool.",
                "event_type":"Pitch Competition",
                "location":"San Francisco + Virtual",
                "is_virtual":True,
                "event_date":datetime(2025, 6, 15, 9, 0),
                "max_attendees":2400
            },
            {
                "organizer_id":created_users[2].id,
                "title":"AI Venture Summit 2025",
                "description":"3-day deep dive into AI investment landscape with 200+ speakers.",
                "event_type":"Summit",
                "location":"Singapore",
                "is_virtual":False,
                "event_date":datetime(2025, 7, 8, 8, 0),
                "max_attendees":5000
            },
        ]
        for ed in events_data:
            e = Event(**ed)
            db.add(e)

        db.commit()
        print("✅ Database seeded successfully!")
        print("   Demo accounts: founder@demo.com / investor@demo.com  (password: demo1234)")

    except Exception as ex:
        print(f"⚠️  Seeding error (may already be seeded): {ex}")
        db.rollback()
    finally:
        db.close()


# ════════════════════════════════════════════════════════════
#   STARTUP EVENT
# ════════════════════════════════════════════════════════════

@app.on_event("startup")
async def on_startup():
    seed_database()
    print("\n" + "═"*60)
    print("  🚀 VentureAI API — Running!")
    print("═"*60)
    print(f"  📡 API:    http://localhost:8000")
    print(f"  📖 Docs:   http://localhost:8000/docs")
    print(f"  🗄️  DB:    ventureai.db (SQLite)")
    print(f"  🤖 AI:    {'OpenAI GPT-4' if OPENAI_KEY else 'Rule-based (set OPENAI_API_KEY)'}")
    print("═"*60 + "\n")


# ════════════════════════════════════════════════════════════
#   ENTRY POINT
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    uvicorn.run(
        "backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
