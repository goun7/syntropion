"""
Unit and integration tests for SYNTROPION OS Dynamic Plugin Loader.
Tests AST validation, runtime Python compilation, live router mounting, and direct execution.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from syntropion_core.plugin_loader import DynamicPluginManager
from syntropion_core.code_synthesizer import validate_python_code_ast
from syntropion_core.database import db


def test_ast_validation_rejects_unsafe_code():
    unsafe_code = """
import os
def exploit():
    os.system("rm -rf /")
"""
    with pytest.raises(ValueError, match="AST Security Violations"):
        validate_python_code_ast(unsafe_code)


def test_dynamic_plugin_load_and_mount_to_app():
    test_app = FastAPI()
    manager = DynamicPluginManager(app=test_app)

    valid_plugin_code = """
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/plugins/test-calc", tags=["test-calc"])

class CalcRequest(BaseModel):
    a: int
    b: int

@router.post("/sum")
async def calculate_sum(req: CalcRequest):
    return {"sum": req.a + req.b, "status": "OK"}
"""
    router = manager.load_plugin_from_code("test-calc", valid_plugin_code)
    assert router is not None
    assert "test-calc" in manager.get_loaded_plugins()

    # Test live execution via FastAPI TestClient
    client = TestClient(test_app)
    response = client.post("/api/v1/plugins/test-calc/sum", json={"a": 15, "b": 27})
    assert response.status_code == 200
    data = response.json()
    assert data["sum"] == 42
    assert data["status"] == "OK"


def test_plugin_missing_router_raises_value_error():
    manager = DynamicPluginManager()
    code_without_router = """
def hello():
    return "world"
"""
    with pytest.raises(ValueError, match="does not export an APIRouter"):
        manager.load_plugin_from_code("no-router", code_without_router)


def test_mount_venture_by_id_and_execute_direct():
    # Use existing seeded pilot venture (e.g. radtrack or lexnotice)
    venture = db.fetchone("SELECT * FROM ventures LIMIT 1")
    assert venture is not None, "Database must have at least one seeded pilot venture"

    test_app = FastAPI()
    manager = DynamicPluginManager(app=test_app)

    # Mount venture
    mount_res = manager.mount_venture_by_id(venture["venture_id"])
    assert mount_res["status"] == "MOUNTED"
    assert mount_res["code_slug"] == venture["code_slug"]
    assert mount_res["routes_count"] >= 1
    assert venture["code_slug"] in manager.get_loaded_plugins()

    # Direct execution
    exec_res = manager.execute_plugin_direct(venture["code_slug"], {"input_metric": 42.5})
    assert exec_res["status"] == "COMPLETED"
    assert exec_res["venture_slug"] == venture["code_slug"]
    assert exec_res["processed_fields"] == 1
    assert exec_res["tenant_execution"] == "OK"


def test_mount_nonexistent_venture_raises_error():
    manager = DynamicPluginManager()
    with pytest.raises(ValueError, match="not found in database"):
        manager.mount_venture_by_id("non-existent-venture-999")

    with pytest.raises(ValueError, match="not found in database"):
        manager.execute_plugin_direct("non-existent-slug-999", {})


def test_execute_plugin_direct_unmounted_triggers_autoload():
    venture = db.fetchone("SELECT * FROM ventures LIMIT 1")
    assert venture is not None

    manager = DynamicPluginManager()
    # Confirm it is not loaded yet
    assert venture["code_slug"] not in manager.get_loaded_plugins()

    # Direct execution must auto-compile and load
    res = manager.execute_plugin_direct(venture["code_slug"], {"field1": 10, "field2": 20})
    assert res["status"] == "COMPLETED"
    assert res["processed_fields"] == 2
    assert venture["code_slug"] in manager.get_loaded_plugins()
