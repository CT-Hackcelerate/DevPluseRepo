"""Focused offline tests for the model-routing skill (Skill 2b)."""

from model_routing.classifier import Complexity, classify_task
from model_routing.router import RouterConfig, route_task


def test_classify_trivial():
    assert classify_task("rename a variable and fix a typo").complexity == Complexity.TRIVIAL


def test_trivial_routes_to_cheap_model():
    cfg = RouterConfig()
    assert route_task("rename the config variable to snake_case", cfg).model == cfg.trivial_model


def test_complex_routes_to_premium_model():
    cfg = RouterConfig()
    route = route_task(
        "Design a distributed transaction protocol with rollback and idempotency", cfg)
    assert route.model == cfg.complex_model


def test_low_confidence_upgrades():
    cfg = RouterConfig()
    route = route_task("implement rename", cfg)
    assert route.upgraded and route.model != cfg.trivial_model
