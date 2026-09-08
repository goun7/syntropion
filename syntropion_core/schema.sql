-- ============================================================================
-- SYNTROPION OS: POSTGRESQL & SQLITE HYBRID PRODUCTION SCHEMA DDL
-- Single-Core Microkernel Multi-Tenant Architecture with Audit Hash Chains
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

-- 1. Sektör Uzmanları Tablosu (5846 FSEK ve 6698 KVKK Uyumlu)
CREATE TABLE IF NOT EXISTS domain_experts (
    expert_id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    phone_number TEXT,
    industry_domain TEXT NOT NULL,
    years_of_experience INTEGER NOT NULL DEFAULT 0,
    stripe_connect_account_id TEXT,
    iban TEXT,
    ip_assignment_signed INTEGER NOT NULL DEFAULT 0,
    ip_assignment_signed_at TEXT,
    fsek_terms_version TEXT NOT NULL DEFAULT 'v1.0-2026',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 2. Sunulan Fikirler ve $10 Stake Emanet Takip Tablosu
CREATE TABLE IF NOT EXISTS domain_ideas (
    idea_id TEXT PRIMARY KEY,
    expert_id TEXT NOT NULL REFERENCES domain_experts(expert_id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    problem_statement TEXT NOT NULL,
    target_audience TEXT NOT NULL,
    current_workaround TEXT,
    stake_amount_usd REAL NOT NULL DEFAULT 10.00,
    stake_payment_status TEXT NOT NULL DEFAULT 'PENDING' CHECK(stake_payment_status IN ('PENDING', 'HELD_IN_ESCROW', 'REFUNDED', 'CAPTURED_TO_EQUITY')),
    stripe_charge_id TEXT,
    status TEXT NOT NULL DEFAULT 'SUBMITTED' CHECK(status IN ('SUBMITTED', 'IN_INTERVIEW', 'APPROVED_FOR_SYNTHESIS', 'REJECTED', 'SYNTHESIZED')),
    domain_depth_score REAL,
    rejection_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 3. Sokratik Mülakat Soru-Cevap ve Derinlik Günlüğü
CREATE TABLE IF NOT EXISTS socratic_interviews (
    interview_id TEXT PRIMARY KEY,
    idea_id TEXT NOT NULL REFERENCES domain_ideas(idea_id) ON DELETE CASCADE,
    question_step INTEGER NOT NULL CHECK (question_step BETWEEN 1 AND 5),
    question_text TEXT NOT NULL,
    expert_response TEXT NOT NULL,
    ai_evaluation_score REAL NOT NULL,
    regulatory_flags TEXT DEFAULT '[]',
    edge_cases_identified TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);

-- 4. Üretilen Mikro-SaaS Girişimleri (Tek Çekirdeğe Bağlı Eklentiler)
CREATE TABLE IF NOT EXISTS ventures (
    venture_id TEXT PRIMARY KEY,
    idea_id TEXT NOT NULL UNIQUE REFERENCES domain_ideas(idea_id) ON DELETE RESTRICT,
    code_slug TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    tagline TEXT,
    docker_container_name TEXT,
    git_commit_sha TEXT,
    api_prefix_path TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'ALPHA_TEST' CHECK(status IN ('DRAFT', 'ALPHA_TEST', 'BETA_PILOT', 'PRODUCTION_LIVE', 'ARCHIVED')),
    target_monthly_mrr_usd REAL DEFAULT 4250.00,
    current_monthly_mrr_usd REAL DEFAULT 0.00,
    active_b2b_subscribers INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 5. Oyunlaştırılmış Hak Ediş ve Ömür Boyu Lisans Takibi
CREATE TABLE IF NOT EXISTS milestone_vestings (
    vesting_id TEXT PRIMARY KEY,
    venture_id TEXT NOT NULL REFERENCES ventures(venture_id) ON DELETE CASCADE,
    expert_id TEXT NOT NULL REFERENCES domain_experts(expert_id) ON DELETE CASCADE,
    milestone_tier INTEGER NOT NULL CHECK (milestone_tier IN (1, 2, 3)),
    description TEXT NOT NULL,
    rev_share_percentage REAL NOT NULL,
    is_unlocked INTEGER NOT NULL DEFAULT 0,
    unlocked_at TEXT,
    proof_verification_data TEXT DEFAULT '{}',
    license_key TEXT,
    created_at TEXT NOT NULL
);

-- 6. Adil Kullanım Token Kotası (Aylık 5M Ücretsiz Token & Overflow)
CREATE TABLE IF NOT EXISTS token_quotas (
    quota_id TEXT PRIMARY KEY,
    expert_id TEXT NOT NULL REFERENCES domain_experts(expert_id) ON DELETE CASCADE,
    venture_id TEXT NOT NULL REFERENCES ventures(venture_id) ON DELETE CASCADE,
    billing_cycle_month TEXT NOT NULL,
    free_token_limit INTEGER NOT NULL DEFAULT 5000000,
    used_tokens INTEGER NOT NULL DEFAULT 0,
    overflow_tokens INTEGER NOT NULL DEFAULT 0,
    overflow_billed_usd REAL NOT NULL DEFAULT 0.0000,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(expert_id, venture_id, billing_cycle_month)
);

-- 7. B2B Müşteri Abonelikleri (Çok Kiracılı Kiracı İzolasyonu)
CREATE TABLE IF NOT EXISTS b2b_subscriptions (
    subscription_id TEXT PRIMARY KEY,
    venture_id TEXT NOT NULL REFERENCES ventures(venture_id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL,
    customer_company_name TEXT NOT NULL,
    customer_tax_id TEXT,
    customer_email TEXT NOT NULL,
    plan_tier TEXT NOT NULL DEFAULT 'STANDARD' CHECK(plan_tier IN ('STARTER', 'STANDARD', 'ENTERPRISE')),
    monthly_price_usd REAL NOT NULL,
    stripe_subscription_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'PAST_DUE', 'CANCELLED')),
    current_period_start TEXT NOT NULL,
    current_period_end TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 8. Otonom Kâr Dağıtımı (%20 Uzman / %75 Hazine / %5 İhtiyat)
CREATE TABLE IF NOT EXISTS revenue_distributions (
    distribution_id TEXT PRIMARY KEY,
    venture_id TEXT NOT NULL REFERENCES ventures(venture_id) ON DELETE CASCADE,
    billing_period TEXT NOT NULL,
    gross_revenue_usd REAL NOT NULL,
    infra_and_llm_costs_usd REAL NOT NULL,
    net_profit_usd REAL NOT NULL,
    expert_rev_share_usd REAL NOT NULL,
    treasury_share_usd REAL NOT NULL,
    reserve_fund_usd REAL NOT NULL,
    stripe_transfer_id TEXT,
    transferred_at TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'PROCESSED', 'FAILED')),
    created_at TEXT NOT NULL
);

-- 9. Değiştirilemez Denetim İzi (Merkle Hash Chain Ledger)
CREATE TABLE IF NOT EXISTS audit_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL
);

-- İndeksler
CREATE INDEX IF NOT EXISTS idx_ideas_expert ON domain_ideas(expert_id);
CREATE INDEX IF NOT EXISTS idx_ideas_status ON domain_ideas(status);
CREATE INDEX IF NOT EXISTS idx_socratic_idea ON socratic_interviews(idea_id);
CREATE INDEX IF NOT EXISTS idx_ventures_slug ON ventures(code_slug);
CREATE INDEX IF NOT EXISTS idx_quotas_expert_month ON token_quotas(expert_id, billing_cycle_month);
CREATE INDEX IF NOT EXISTS idx_subs_tenant ON b2b_subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dist_venture_period ON revenue_distributions(venture_id, billing_period);
