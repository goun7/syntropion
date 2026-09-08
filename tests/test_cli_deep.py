"""
Deep tests for syntropion_core.cli functions.
"""

import pytest
from unittest.mock import patch, MagicMock
from syntropion_core.cli import (
    cmd_init_db, cmd_seed_pilots, cmd_list_ventures,
    cmd_submit_idea, cmd_run_interview, cmd_dist_revenue,
    main
)


def test_cli_functions_direct():
    args = MagicMock()
    cmd_init_db(args)
    cmd_seed_pilots(args)
    cmd_list_ventures(args)

    # Submit idea
    args.title = "CLI Test Idea"
    args.problem = "Some field problem for doctors with 5 hours loss"
    args.audience = "Hospitals"
    args.expert_email = "cli_expert@test.com"
    args.expert_name = "Dr. CLI"
    args.domain = "healthcare"
    args.exp = 12
    cmd_submit_idea(args)

    # Socratic interview
    from syntropion_core.database import db
    idea = db.fetchone("SELECT idea_id FROM domain_ideas WHERE expert_id LIKE 'exp-cli-%' ORDER BY created_at DESC")
    if idea:
        args.idea_id = idea["idea_id"]
        args.step = 1
        args.response = "RECIST 1.1 kriterlerinde BT lezyon ölçümü 2 saat sürüyor."
        cmd_run_interview(args)

    # Dist revenue
    args.venture_id = "ven-pilot-001-radtrack"
    args.period = "2026-11"
    args.gross = 1000.0
    args.costs = 100.0
    cmd_dist_revenue(args)


def test_cli_main_dispatch():
    with patch("sys.argv", ["syntropion", "list-ventures"]):
        main()
