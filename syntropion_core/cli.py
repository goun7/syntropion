"""
SYNTROPION OS — Command Line Interface (CLI)
Studio operations, pilot seeding, proposal management, and server orchestration.
"""

import sys
import argparse
import json
from syntropion_core.database import db
from syntropion_core.stake_gate import stake_gate
from syntropion_core.socratic_engine import socratic_engine
from syntropion_core.code_synthesizer import code_synthesizer
from syntropion_core.vesting_engine import vesting_engine
from syntropion_core.revenue_router import revenue_router


def cmd_init_db(args):
    """Initializes the database schema."""
    print("Initializing SYNTROPION OS database schema...")
    db._ensure_schema()
    print(f"Schema initialized successfully at: {db.db_path}")


def cmd_seed_pilots(args):
    """Seeds the 5 deep vertical pilots from Chapter 23 of Fikir.md."""
    print("Seeding 5 Deep Vertical Pilots (RadTrack, LexNotice, TaxCrossAudit, TarifaCustoms, DemurrageShield)...")
    db.seed_deep_vertical_pilots()
    ventures = db.fetchall("SELECT display_name, code_slug, current_monthly_mrr_usd FROM ventures")
    print(f"Successfully seeded {len(ventures)} ventures:")
    for v in ventures:
        print(f" - [{v['code_slug']}] {v['display_name']} -> ${v['current_monthly_mrr_usd']:,.2f} MRR")


def cmd_list_ventures(args):
    """Lists all registered micro-SaaS ventures — MRR değerleri dürüstçe etiketlenir."""
    # DURUST (AT-HONEST-001): MRR iddialarını gerçek abonelik satırlarıyla
    # kıyasla; doğrulanmayan değer "[simülasyon]" etiketiyle gösterilir.
    from syntropion_core.honest_metrics import mrr_provenance
    prov = mrr_provenance()

    ventures = db.fetchall("SELECT venture_id, code_slug, display_name, status, current_monthly_mrr_usd, active_b2b_subscribers FROM ventures ORDER BY current_monthly_mrr_usd DESC")
    print("\n" + "=" * 110)
    print(f"{'SLUG':<20} | {'DISPLAY NAME':<26} | {'STATUS':<15} | {'MRR (USD)':<12} | {'SUBS':<6}")
    print("=" * 110)
    for v in ventures:
        # DURUST: abonelik tablosu boşken MRR>0 → uydurma işareti konur.
        tag = ""
        if v["current_monthly_mrr_usd"] > 0 and prov["active_subscription_rows"] == 0:
            tag = "  [simülasyon — b2b_subscriptions=0]"
        print(f"{v['code_slug']:<20} | {v['display_name'][:26]:<26} | {v['status']:<15} | ${v['current_monthly_mrr_usd']:<11.2f} | {v['active_b2b_subscribers']:<6}{tag}")
    print("=" * 110)
    # DURUST: kanıt zeminini göster
    print(f"  DOĞRULANAN MRR (ACTIVE b2b_subscriptions): ${prov['verified_mrr_usd']:,.2f} "
          f"| iddia: ${prov['claimed_mrr_usd']:,.2f} | verdict: {prov['verdict']}")
    print("  DURUST: MRR değerleri demo seed sabitleridir; gerçek abonelik verisi yok.\n")


def cmd_honest_metrics(args):
    """Dürüst metrik raporunu göster — uydurma değer içermez."""
    from syntropion_core.honest_metrics import render_honest_report
    print(render_honest_report())


def cmd_submit_idea(args):
    """Submits a domain proposal from CLI."""
    print(f"Submitting domain idea: '{args.title}' by {args.expert_email}...")
    from syntropion_core.schemas import ProposalSubmitRequest, DomainExpertCreate
    from syntropion_core.security import scrub_pii_presidio_grade, generate_fsek_clickwrap_hash
    from syntropion_core.database import get_current_iso_time
    import uuid

    now = get_current_iso_time()
    existing = db.fetchone("SELECT expert_id FROM domain_experts WHERE email = ?", (args.expert_email,))
    if existing:
        expert_id = existing["expert_id"]
    else:
        expert_id = f"exp-cli-{uuid.uuid4().hex[:8]}"
        db.execute(
            """
            INSERT INTO domain_experts (
                expert_id, email, full_name, industry_domain, years_of_experience,
                ip_assignment_signed, ip_assignment_signed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (expert_id, args.expert_email, args.expert_name, args.domain, args.exp, now, now, now)
        )

    idea_id = f"idea-cli-{uuid.uuid4().hex[:8]}"
    scrubbed, _ = scrub_pii_presidio_grade(args.problem)
    db.execute(
        """
        INSERT INTO domain_ideas (
            idea_id, expert_id, title, problem_statement, target_audience,
            stake_amount_usd, stake_payment_status, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 10.00, 'HELD_IN_ESCROW', 'SUBMITTED', ?, ?)
        """,
        (idea_id, expert_id, args.title, scrubbed, args.audience, now, now)
    )
    print(f"Idea created successfully: {idea_id} (Stake: $10 HELD_IN_ESCROW)")
    print(f"Run Socratic Step 1: syntropion interview --idea-id {idea_id} --step 1 --response '<yanıt>'")


def cmd_run_interview(args):
    """Processes a Socratic interview step."""
    print(f"Evaluating Socratic Step {args.step} for Idea {args.idea_id}...")
    res = socratic_engine.process_step(args.idea_id, args.step, args.response)
    print(f" - Step Score: {res['score']:.2f}")
    print(f" - Running DDS: {res['domain_depth_score_running']:.2f}")
    print(f" - Status: {res['status']}")
    print(f" - Feedback: {res['feedback']}")
    if res['next_question']:
        print(f"\nNext Question (Step {args.step + 1}):\n{res['next_question']}")


def cmd_dist_revenue(args):
    """Processes monthly revenue split for a venture."""
    print(f"Processing revenue split for venture {args.venture_id} (Period: {args.period})...")
    res = revenue_router.calculate_and_record_split(
        venture_id=args.venture_id,
        billing_period=args.period,
        gross_revenue_usd=args.gross,
        infra_costs_usd=args.costs
    )
    print(json.dumps(res, indent=2))


def cmd_run_server(args):
    """Runs the FastAPI + Uvicorn server."""
    import uvicorn
    print(f"Starting SYNTROPION OS Server on {args.host}:{args.port}...")
    uvicorn.run("syntropion_core.api:app", host=args.host, port=args.port, reload=args.reload)


def main():
    parser = argparse.ArgumentParser(prog="syntropion", description="SYNTROPION OS — Autonomous Venture Studio CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init-db
    p_init = subparsers.add_parser("init-db", help="Initialize SQLite WAL database schema")
    p_init.set_defaults(func=cmd_init_db)

    # seed-pilots
    p_seed = subparsers.add_parser("seed-pilots", help="Seed 5 deep vertical pilots")
    p_seed.set_defaults(func=cmd_seed_pilots)

    # list-ventures
    p_list = subparsers.add_parser("list-ventures", help="List active micro-SaaS ventures")
    p_list.set_defaults(func=cmd_list_ventures)

    # honest-metrics (AT-HONEST-001)
    p_hm = subparsers.add_parser("honest-metrics", help="Dürüst metrik raporu — uydurma değer içermez")
    p_hm.set_defaults(func=cmd_honest_metrics)

    # submit-idea
    p_sub = subparsers.add_parser("submit-idea", help="Submit a new domain proposal")
    p_sub.add_argument("--title", required=True, help="Idea title")
    p_sub.add_argument("--problem", required=True, help="Problem statement")
    p_sub.add_argument("--audience", required=True, help="Target audience")
    p_sub.add_argument("--expert-email", required=True, help="Expert email")
    p_sub.add_argument("--expert-name", default="Saha Uzmanı", help="Expert full name")
    p_sub.add_argument("--domain", default="general", help="Domain sector")
    p_sub.add_argument("--exp", type=int, default=10, help="Years of experience")
    p_sub.set_defaults(func=cmd_submit_idea)

    # interview
    p_int = subparsers.add_parser("interview", help="Run a Socratic interview step")
    p_int.add_argument("--idea-id", required=True, help="Idea ID")
    p_int.add_argument("--step", type=int, required=True, choices=[1, 2, 3, 4, 5], help="Step number")
    p_int.add_argument("--response", required=True, help="Expert response text")
    p_int.set_defaults(func=cmd_run_interview)

    # dist-revenue
    p_rev = subparsers.add_parser("dist-revenue", help="Calculate and distribute monthly revenue split")
    p_rev.add_argument("--venture-id", required=True, help="Venture ID")
    p_rev.add_argument("--period", required=True, help="Billing period YYYY-MM")
    p_rev.add_argument("--gross", type=float, required=True, help="Gross revenue in USD")
    p_rev.add_argument("--costs", type=float, default=0.0, help="Infra costs in USD")
    p_rev.set_defaults(func=cmd_dist_revenue)

    # run-server
    p_run = subparsers.add_parser("run-server", help="Run HTTP server")
    p_run.add_argument("--host", default="0.0.0.0", help="Host address")
    p_run.add_argument("--port", type=int, default=8000, help="Port")
    p_run.add_argument("--reload", action="store_true", help="Enable reload")
    p_run.set_defaults(func=cmd_run_server)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
