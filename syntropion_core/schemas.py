"""
SYNTROPION OS — Pydantic V2 Schemas & Data Contracts
Strict type-safe contracts for Proposals, Socratic Steps, Ventures, Quotas, and Revenues.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from decimal import Decimal


# --- 1. Expert & Proposal Contracts ---

class DomainExpertCreate(BaseModel):
    email: str = Field(..., pattern=r"^[\w\.\+-]+@[\w\.-]+\.\w+$")
    full_name: str = Field(..., min_length=2, max_length=150)
    phone_number: Optional[str] = None
    industry_domain: str = Field(..., min_length=2, max_length=100)
    years_of_experience: int = Field(..., ge=0, le=70)
    iban: Optional[str] = None
    ip_assignment_signed: bool = True
    fsek_terms_version: str = "v1.0-2026"


class ProposalSubmitRequest(BaseModel):
    expert: DomainExpertCreate
    title: str = Field(..., min_length=5, max_length=255)
    problem_statement: str = Field(..., min_length=20)
    target_audience: str = Field(..., min_length=5, max_length=255)
    current_workaround: Optional[str] = None
    stake_amount_usd: float = Field(default=10.00, ge=5.00, le=100.00)
    stripe_payment_method_id: Optional[str] = "pm_mock_card_test_success"
    fsek_clickwrap_accepted: bool = True


class ProposalSubmitResponse(BaseModel):
    status: Literal["SUCCESS", "FAILED"]
    idea_id: str
    expert_id: str
    stake_status: str
    amount_held_usd: float
    next_step: str
    interview_session_url: str
    fsek_contract_hash: str


# --- 2. Socratic Interrogation Contracts ---

class SocraticStepRequest(BaseModel):
    idea_id: str
    step: int = Field(..., ge=1, le=5)
    expert_response: str = Field(..., min_length=10)


class SocraticEvaluationResult(BaseModel):
    step: int
    question_text: str
    score: float = Field(..., ge=0.0, le=1.0)
    domain_depth_score_running: float
    regulatory_flags: List[str] = []
    edge_cases_identified: List[str] = []
    is_completed: bool
    status: Literal["IN_PROGRESS", "PASSED_THRESHOLD", "REJECTED_LOW_SCORE"]
    feedback: str
    next_question: Optional[str] = None


# --- 3. Stake Management Contracts ---

class StakeStatusResponse(BaseModel):
    idea_id: str
    stake_amount_usd: float
    status: Literal["PENDING", "HELD_IN_ESCROW", "REFUNDED", "CAPTURED_TO_EQUITY"]
    stripe_charge_id: Optional[str] = None
    refund_transaction_id: Optional[str] = None
    decision_reason: Optional[str] = None


# --- 4. Venture & Synthesis Contracts ---

class VentureSynthesizeRequest(BaseModel):
    idea_id: str
    target_slug: Optional[str] = None
    auto_deploy_container: bool = False


class VentureResponse(BaseModel):
    venture_id: str
    idea_id: str
    code_slug: str
    display_name: str
    tagline: Optional[str] = None
    api_prefix_path: str
    status: str
    current_monthly_mrr_usd: float
    active_b2b_subscribers: int
    created_at: str


class GeneratedCodeArtifact(BaseModel):
    venture_slug: str
    openapi_spec: Dict[str, Any]
    fastapi_router_code: str
    test_suite_code: str
    ast_validation_passed: bool


# --- 5. Milestone Vesting & Quota Contracts ---

class MilestoneUnlockRequest(BaseModel):
    venture_id: str
    expert_id: str
    tier: int = Field(..., ge=1, le=3)
    proof_data: Dict[str, Any] = {}


class VestingStatusResponse(BaseModel):
    venture_id: str
    expert_id: str
    unlocked_rev_share_pct: float
    lifetime_license_key: Optional[str] = None
    active_milestones: List[Dict[str, Any]] = []


class QuotaConsumeRequest(BaseModel):
    expert_id: str
    venture_id: str
    tokens_requested: int = Field(..., gt=0)


class QuotaStatusResponse(BaseModel):
    expert_id: str
    venture_id: str
    billing_month: str
    free_token_limit: int
    used_tokens: int
    remaining_free_tokens: int
    overflow_tokens: int
    overflow_billed_usd: float
    is_throttled: bool
    alert_level: Literal["NORMAL", "WARNING_80_PCT", "DEPLETED_100_PCT"]


# --- 6. Revenue Distribution Contracts ---

class RevenueCalculateRequest(BaseModel):
    venture_id: str
    billing_period: str
    gross_revenue_usd: float = Field(..., ge=0.0)
    infra_costs_usd: float = Field(default=0.0, ge=0.0)


class RevenueDistributionResponse(BaseModel):
    distribution_id: str
    venture_id: str
    billing_period: str
    gross_revenue_usd: float
    infra_and_llm_costs_usd: float
    net_profit_usd: float
    expert_rev_share_usd: float
    treasury_share_usd: float
    reserve_fund_usd: float
    status: str
    ipc_telemetry_dispatched: bool


# --- 7. Programmatic B2B GTM Swarm Contracts ---

class OutboundLeadCampaignRequest(BaseModel):
    venture_id: str
    target_industry: str
    sample_prospect_company: str
    decision_maker_title: str


class LeadOutreachResponse(BaseModel):
    campaign_id: str
    prospect_company: str
    cold_email_subject: str
    cold_email_body: str
    spam_score_penalty: float
    deliverability_score: float
    projected_conversion_rate: float
    pipeline_stage: str
