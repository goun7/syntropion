"""
SYNTROPION OS — Production FastAPI REST API
Single-Core Microkernel Router orchestrating Proposals, Socratic Steps, Synthesis, Vesting, Quotas, and Revenue.
"""

import os
import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from syntropion_core.database import db, get_current_iso_time
from syntropion_core.schemas import (
    ProposalSubmitRequest, ProposalSubmitResponse,
    SocraticStepRequest, SocraticEvaluationResult,
    VentureSynthesizeRequest, VentureResponse,
    MilestoneUnlockRequest, VestingStatusResponse,
    QuotaConsumeRequest, QuotaStatusResponse,
    RevenueCalculateRequest, RevenueDistributionResponse,
    OutboundLeadCampaignRequest, LeadOutreachResponse
)
from syntropion_core.security import (
    generate_fsek_clickwrap_hash,
    scrub_pii_presidio_grade,
    verify_lifetime_license_key
)
from syntropion_core.stake_gate import stake_gate
from syntropion_core.socratic_engine import socratic_engine
from syntropion_core.code_synthesizer import code_synthesizer, pilot_engines
from syntropion_core.vesting_engine import vesting_engine
from syntropion_core.quota_governor import quota_governor
from syntropion_core.revenue_router import revenue_router
from syntropion_core.shared_memory_ipc import shm_ipc_bridge
from syntropion_core.gtm_swarm import gtm_swarm

app = FastAPI(
    title="SYNTROPION OS API",
    description="Autonomous AI Venture Studio & Micro-SaaS Factory Operating System",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware for Web Cockpit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.exists(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


# --- System & Metrics Endpoints ---

@app.get("/healthz")
async def health_check() -> Dict[str, Any]:
    """Liveness probe returning system status."""
    return {
        "status": "HEALTHY",
        "service": "syntropion-os-core",
        "version": "1.0.0",
        "timestamp": get_current_iso_time()
    }


@app.get("/metrics")
async def system_metrics() -> Dict[str, Any]:
    """Returns studio operational performance indicators."""
    experts_count = db.fetchone("SELECT COUNT(*) as cnt FROM domain_experts")["cnt"]
    ideas_count = db.fetchone("SELECT COUNT(*) as cnt FROM domain_ideas")["cnt"]
    ventures_count = db.fetchone("SELECT COUNT(*) as cnt FROM ventures")["cnt"]
    
    rev_sum = db.fetchone("SELECT SUM(current_monthly_mrr_usd) as total_mrr, SUM(active_b2b_subscribers) as total_subs FROM ventures")
    total_mrr = rev_sum["total_mrr"] or 0.0
    total_subs = rev_sum["total_subs"] or 0

    payouts_sum = db.fetchone("SELECT SUM(expert_rev_share_usd) as expert_payouts, SUM(treasury_share_usd) as treasury_transfers FROM revenue_distributions")
    expert_payouts = payouts_sum["expert_payouts"] or 0.0
    treasury_transfers = payouts_sum["treasury_transfers"] or 0.0

    return {
        "total_domain_experts": experts_count,
        "total_proposals_submitted": ideas_count,
        "active_micro_saas_ventures": ventures_count,
        "portfolio_total_mrr_usd": round(total_mrr, 2),
        "total_active_b2b_subscribers": total_subs,
        "total_expert_rev_share_paid_usd": round(expert_payouts, 2),
        "total_treasury_accumulated_usd": round(treasury_transfers, 2),
        "timestamp": get_current_iso_time()
    }


# --- Proposals & Stake Gate Endpoints ---

@app.post("/api/v1/proposals/submit", response_model=ProposalSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_domain_proposal(payload: ProposalSubmitRequest, req: Request) -> ProposalSubmitResponse:
    """Submits a crowdsourced domain idea, authorizes $10 stake hold, and stamps FSEK agreement."""
    client_ip = req.client.host if req.client else "127.0.0.1"
    now = get_current_iso_time()

    # 1. PII Scrubbing of the problem statement before persistence
    scrubbed_problem, _ = scrub_pii_presidio_grade(payload.problem_statement)
    scrubbed_workaround, _ = scrub_pii_presidio_grade(payload.current_workaround or "")

    # 2. Register or update Expert
    expert_id = f"exp-{uuid.uuid4().hex[:10]}"
    existing = db.fetchone("SELECT expert_id FROM domain_experts WHERE email = ?", (payload.expert.email,))
    if existing:
        expert_id = existing["expert_id"]
    else:
        db.execute(
            """
            INSERT INTO domain_experts (
                expert_id, email, full_name, phone_number, industry_domain,
                years_of_experience, iban, ip_assignment_signed, ip_assignment_signed_at,
                fsek_terms_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expert_id, payload.expert.email, payload.expert.full_name,
                payload.expert.phone_number, payload.expert.industry_domain,
                payload.expert.years_of_experience, payload.expert.iban,
                1 if payload.expert.ip_assignment_signed else 0,
                now, payload.expert.fsek_terms_version, now, now
            )
        )

    # 3. Create Idea Record
    idea_id = f"idea-{uuid.uuid4().hex[:10]}"
    db.execute(
        """
        INSERT INTO domain_ideas (
            idea_id, expert_id, title, problem_statement, target_audience,
            current_workaround, stake_amount_usd, stake_payment_status, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', 'SUBMITTED', ?, ?)
        """,
        (
            idea_id, expert_id, payload.title, scrubbed_problem,
            payload.target_audience, scrubbed_workaround, payload.stake_amount_usd,
            now, now
        )
    )

    # 4. Hold $10 Stake in Escrow
    stake_res = stake_gate.hold_stake_in_escrow(
        idea_id=idea_id,
        expert_id=expert_id,
        amount_usd=payload.stake_amount_usd,
        payment_method_id=payload.stripe_payment_method_id or "pm_mock"
    )

    # 5. Generate FSEK Clickwrap Cryptographic Proof
    fsek_hash = generate_fsek_clickwrap_hash(payload.expert.email, now, client_ip)

    return ProposalSubmitResponse(
        status="SUCCESS",
        idea_id=idea_id,
        expert_id=expert_id,
        stake_status=stake_res["status"],
        amount_held_usd=stake_res["amount_usd"],
        next_step="SOCRATIC_INTERVIEW_STEP_1",
        interview_session_url=f"/interview/{idea_id}",
        fsek_contract_hash=fsek_hash
    )


@app.get("/api/v1/proposals")
async def list_proposals() -> List[Dict[str, Any]]:
    """Lists all submitted domain proposals."""
    return db.fetchall("SELECT * FROM domain_ideas ORDER BY created_at DESC")


@app.get("/api/v1/proposals/{idea_id}")
async def get_proposal(idea_id: str) -> Dict[str, Any]:
    """Gets details for a single domain proposal."""
    idea = db.fetchone("SELECT * FROM domain_ideas WHERE idea_id = ?", (idea_id,))
    if not idea:
        raise HTTPException(status_code=404, detail="Proposal not found")
    interviews = db.fetchall("SELECT * FROM socratic_interviews WHERE idea_id = ? ORDER BY question_step ASC", (idea_id,))
    return {"idea": idea, "interview_steps": interviews}


# --- Socratic Interview Endpoints ---

@app.get("/api/v1/interview/question/{step}")
async def get_interview_question(step: int) -> Dict[str, Any]:
    """Retrieves question details for a Socratic step (1 to 5)."""
    try:
        q = socratic_engine.get_question(step)
        return {"step": step, "question": q}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/interview/step", response_model=SocraticEvaluationResult)
async def process_socratic_step(payload: SocraticStepRequest) -> SocraticEvaluationResult:
    """Submits answer to a Socratic question, calculates score & updates DDS."""
    try:
        res = socratic_engine.process_step(
            idea_id=payload.idea_id,
            step=payload.step,
            expert_response=payload.expert_response
        )
        return SocraticEvaluationResult(**res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Ventures & Code Synthesis Endpoints ---

@app.post("/api/v1/ventures/synthesize")
async def synthesize_venture_code(payload: VentureSynthesizeRequest) -> Dict[str, Any]:
    """Synthesizes deterministic micro-SaaS plugin code for an approved proposal."""
    try:
        res = code_synthesizer.synthesize_venture(
            idea_id=payload.idea_id,
            custom_slug=payload.target_slug
        )
        # Initialize milestone vesting tiers
        idea = db.fetchone("SELECT expert_id FROM domain_ideas WHERE idea_id = ?", (payload.idea_id,))
        vesting_engine.initialize_venture_vestings(res["venture_id"], idea["expert_id"])
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/ventures")
async def list_ventures() -> List[Dict[str, Any]]:
    """Lists all synthesized micro-SaaS ventures."""
    return db.fetchall("SELECT * FROM ventures ORDER BY created_at DESC")


@app.get("/api/v1/ventures/{venture_id}")
async def get_venture_details(venture_id: str) -> Dict[str, Any]:
    """Gets details, subscribers, and quotas for a venture."""
    venture = db.fetchone("SELECT * FROM ventures WHERE venture_id = ?", (venture_id,))
    if not venture:
        raise HTTPException(status_code=404, detail="Venture not found")
    vestings = db.fetchall("SELECT * FROM milestone_vestings WHERE venture_id = ?", (venture_id,))
    distributions = db.fetchall("SELECT * FROM revenue_distributions WHERE venture_id = ? ORDER BY billing_period DESC", (venture_id,))
    return {"venture": venture, "vestings": vestings, "distributions": distributions}


# --- Gamified Milestone Vesting Endpoints ---

@app.post("/api/v1/vesting/unlock")
async def unlock_vesting_tier(payload: MilestoneUnlockRequest) -> Dict[str, Any]:
    """Unlocks a milestone tier (1, 2, or 3), releasing rev-share and license key."""
    try:
        res = vesting_engine.unlock_milestone(
            venture_id=payload.venture_id,
            expert_id=payload.expert_id,
            tier=payload.tier,
            proof_data=payload.proof_data
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/vesting/{venture_id}/{expert_id}")
async def get_vesting_status(venture_id: str, expert_id: str) -> Dict[str, Any]:
    """Returns unlocked rev-share and license key for an expert."""
    return vesting_engine.get_expert_vesting_status(venture_id, expert_id)


# --- Token Quota Governor Endpoints ---

@app.get("/api/v1/quotas/{expert_id}/{venture_id}", response_model=QuotaStatusResponse)
async def check_token_quota(expert_id: str, venture_id: str) -> QuotaStatusResponse:
    """Returns monthly 5M token quota usage and overflow metering status."""
    res = quota_governor.get_status(expert_id, venture_id)
    return QuotaStatusResponse(**res)


@app.post("/api/v1/quotas/consume", response_model=QuotaStatusResponse)
async def consume_tokens(payload: QuotaConsumeRequest) -> QuotaStatusResponse:
    """Consumes tokens from the free monthly quota pool."""
    try:
        res = quota_governor.consume_tokens(
            expert_id=payload.expert_id,
            venture_id=payload.venture_id,
            token_count=payload.tokens_requested
        )
        return QuotaStatusResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Revenue Router & Shared Memory IPC Endpoints ---

@app.post("/api/v1/revenue/calculate", response_model=RevenueDistributionResponse)
async def process_revenue_split(payload: RevenueCalculateRequest) -> RevenueDistributionResponse:
    """Executes the 20% Expert / 75% Treasury / 5% Reserve revenue split."""
    try:
        res = revenue_router.calculate_and_record_split(
            venture_id=payload.venture_id,
            billing_period=payload.billing_period,
            gross_revenue_usd=payload.gross_revenue_usd,
            infra_costs_usd=payload.infra_costs_usd
        )
        return RevenueDistributionResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/revenue/history/{venture_id}")
async def get_revenue_history(venture_id: str) -> List[Dict[str, Any]]:
    """Returns past revenue distributions for a venture."""
    return revenue_router.get_venture_history(venture_id)


@app.get("/api/v1/revenue/telemetry/latest")
async def get_latest_ipc_telemetry() -> Dict[str, Any]:
    """Reads the latest zero-copy POSIX shared memory telemetry packet."""
    pkt = shm_ipc_bridge.read_latest_telemetry()
    return {"latest_shm_packet": pkt}


# --- Programmatic GTM Swarm Endpoints ---

@app.post("/api/v1/gtm/campaign", response_model=LeadOutreachResponse)
async def create_gtm_campaign(payload: OutboundLeadCampaignRequest) -> LeadOutreachResponse:
    """Generates a high-converting cold outreach sequence tailored to target vertical."""
    venture = db.fetchone("SELECT * FROM ventures WHERE venture_id = ?", (payload.venture_id,))
    venture_slug = venture["code_slug"] if venture else "micro-saas"

    res = gtm_swarm.generate_campaign(
        venture_slug=venture_slug,
        prospect_company=payload.sample_prospect_company,
        decision_maker_title=payload.decision_maker_title,
        industry_domain=payload.target_industry
    )
    return LeadOutreachResponse(**res)


@app.get("/api/v1/gtm/simulate")
async def simulate_gtm_funnel(leads: int = 100) -> Dict[str, Any]:
    """Simulates B2B funnel conversion from cold lead to paying subscriber."""
    return gtm_swarm.simulate_pipeline_conversion(leads_count=leads)


# --- 5 Deep Vertical Pilots Live Execution Endpoints ---

class RadTrackInput(BaseModel):
    baseline_mm: float
    follow_up_mm: float

class LexNoticeInput(BaseModel):
    delivery_date: str
    current_date: str
    invoice_amount_try: float

class TaxCrossInput(BaseModel):
    gib_invoices_total_try: float
    accounting_ledger_total_try: float

class TarifaInput(BaseModel):
    product_description: str
    country_of_origin: str

class DemurrageInput(BaseModel):
    discharge_date: str
    gate_out_date: str
    free_time_days: int = 7
    daily_rate_usd: float = 180.0


@app.post("/api/v1/pilots/radtrack")
async def run_radtrack_pilot(inp: RadTrackInput) -> Dict[str, Any]:
    """Executes RadTrack AI RECIST 1.1 Lesion Comparator."""
    try:
        return pilot_engines.execute_radtrack_recist(inp.baseline_mm, inp.follow_up_mm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/pilots/lexnotice")
async def run_lexnotice_pilot(inp: LexNoticeInput) -> Dict[str, Any]:
    """Executes LexNotice AI TTK Default and Statute of Limitations Calculator."""
    try:
        return pilot_engines.execute_lexnotice_ttb(inp.delivery_date, inp.current_date, inp.invoice_amount_try)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/pilots/taxcross")
async def run_taxcross_pilot(inp: TaxCrossInput) -> Dict[str, Any]:
    """Executes TaxCrossAudit KDV & Ba-Bs e-Fatura Reconciliation."""
    return pilot_engines.execute_taxcross_reconciliation(inp.gib_invoices_total_try, inp.accounting_ledger_total_try)


@app.post("/api/v1/pilots/tarifa")
async def run_tarifa_pilot(inp: TarifaInput) -> Dict[str, Any]:
    """Executes TarifaCustoms AI 12-Digit HS Code Classifier."""
    return pilot_engines.execute_tarifa_customs_gtip(inp.product_description, inp.country_of_origin)


@app.post("/api/v1/pilots/demurrage")
async def run_demurrage_pilot(inp: DemurrageInput) -> Dict[str, Any]:
    """Executes DemurrageShield Port Detention & Demurrage Calculator."""
    try:
        return pilot_engines.execute_demurrage_calculation(
            inp.discharge_date, inp.gate_out_date, inp.free_time_days, inp.daily_rate_usd
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Web Portal Root Serving ---

@app.get("/")
async def serve_index() -> FileResponse:
    """Serves the Syntropion OS Web Dashboard."""
    index_file = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse(content={"message": "Syntropion OS Core API is running. Web UI not found."})
