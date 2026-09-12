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


def test_cli_new_expert_submit():
    import uuid
    from syntropion_core.cli import cmd_submit_idea
    args = MagicMock()
    args.title = "CLI New Expert Idea"
    args.problem = "Some field problem with 10 hours loss"
    args.audience = "Lawyers"
    args.expert_email = f"new_expert_{uuid.uuid4().hex[:6]}@lawfirm.com"
    args.expert_name = "Av. Yeni"
    args.domain = "legal"
    args.exp = 8
    cmd_submit_idea(args)


def test_cli_run_server():
    from syntropion_core.cli import cmd_run_server
    args = MagicMock()
    args.host = "127.0.0.1"
    args.port = 8000
    args.reload = False
    with patch("uvicorn.run") as mock_uvicorn:
        cmd_run_server(args)
        mock_uvicorn.assert_called_once_with(
            "syntropion_core.api:app", host="127.0.0.1", port=8000, reload=False
        )


def test_cli_main_dispatch():
    with patch("sys.argv", ["syntropion", "list-ventures"]):
        main()

    # When no arguments are provided, main prints help and exits with 0
    with patch("sys.argv", ["syntropion"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
