"""Sample PRDs from two Business Units — the A/B validation dataset.

Eight feature-request PRDs, deliberately verbose (as real PRDs are), split
across two BUs (Payments and Platform). Each pairs a raw PRD with the concrete
task the AI is asked to plan. These drive ``run_ab_suite`` to demonstrate the
cost/quality claims without any external systems.
"""

from __future__ import annotations

from .ab_runner import TestCase

# ── BU 1: Payments ───────────────────────────────────────────────────────────

_PAYMENTS_CHECKOUT = TestCase(
    name="checkout-retry",
    bu="Payments",
    task="Implement automatic retry with idempotency for failed checkout charges",
    prd="""
Executive Summary

This document describes, at a very high level, the background and context around
the payment checkout experience. As mentioned previously, and as noted in prior
documents, the checkout flow is extremely important to the business.

Background

Basically, customers sometimes experience failed charges at checkout. It should
be noted that this is a recurring pain point that has been raised many times.

Requirements

- The system must automatically retry a failed charge up to 3 times.
- Each retry must be idempotent so a customer is never double-charged.
- The system must not retry charges that failed due to insufficient funds.
- Acceptance criteria: Given a transient gateway error, when a charge fails,
  then the system should retry with the same idempotency key and succeed once.
- Retries must complete within 30 seconds total.
- This depends on the existing PaymentGateway integration.

Out of scope

- We will not change the refund flow in this iteration.
""",
)

_PAYMENTS_FRAUD = TestCase(
    name="fraud-scoring",
    bu="Payments",
    task="Add a real-time fraud risk score to each transaction",
    prd="""
Overview

For reference, this PRD covers fraud scoring. Please note that fraud is a large
number of our chargebacks.

Requirements

- The system must compute a fraud risk score for every transaction in real time.
- The score must be available within 200ms (performance constraint).
- Transactions scoring above the threshold must be flagged for manual review.
- Acceptance criteria: Given a high-risk transaction, when it is submitted,
  then the system should flag it and hold funds.
- This requires integration with the RiskEngine service.
- Security: all scoring inputs must be encrypted in transit.

Out of scope

- Machine-learning model training is not in scope; use the existing model.
""",
)

_PAYMENTS_WALLET = TestCase(
    name="wallet-topup",
    bu="Payments",
    task="Add a stored-value wallet with top-up",
    prd="""
Introduction

This is a lengthy introduction that restates, essentially, the same context we
have covered in many other documents. Obviously the wallet is important.

Requirements

- Users can top up a wallet balance from a saved card.
- The system must record every wallet transaction in an immutable ledger.
- A top-up must not exceed the configured per-day limit.
- Acceptance criteria: Given a user at their daily limit, when they attempt a
  top-up, then the system should reject it with a clear error.
- Wallet balances must be consistent under concurrent top-ups (no lost updates).

Out of scope

- Cross-currency wallets are excluded for now.
""",
)

_PAYMENTS_PAYOUT = TestCase(
    name="scheduled-payout",
    bu="Payments",
    task="Support scheduled payouts to merchants",
    prd="""
Context

Needless to say, merchants want to be paid on a schedule. Generally speaking
this has been requested for a long time.

Requirements

- The system must support daily and weekly scheduled payouts to merchants.
- Payouts must be idempotent to avoid double-paying a merchant.
- A payout must not be issued if the merchant account is under review.
- Acceptance criteria: Given a scheduled weekly payout, when the schedule fires,
  then the system should create exactly one payout for the period.
- Depends on the existing Ledger service and the BankTransfer integration.
""",
)

# ── BU 2: Platform ───────────────────────────────────────────────────────────

_PLATFORM_SSO = TestCase(
    name="sso-login",
    bu="Platform",
    task="Add SSO login via SAML",
    prd="""
Executive Summary

This document, at the present time, describes single sign-on. As noted, SSO is
a frequently requested capability across the organisation.

Requirements

- Users can log in via a SAML identity provider.
- The system must provision a user account on first successful SSO login.
- Authentication tokens must expire after 8 hours.
- Acceptance criteria: Given a valid SAML assertion, when a user logs in,
  then the system should create a session and redirect to the dashboard.
- Security: assertions must be signature-verified before trust.
- This depends on the existing SessionManager component.

Out of scope

- SCIM user provisioning is out of scope for this iteration.
""",
)

_PLATFORM_AUDIT = TestCase(
    name="audit-log",
    bu="Platform",
    task="Add an immutable audit log for admin actions",
    prd="""
Background

It is important to note that compliance requires an audit trail. For the purpose
of this document we focus on admin actions.

Requirements

- The system must record every admin action in an append-only audit log.
- Each entry must capture actor, action, timestamp, and target.
- Audit entries must not be editable or deletable (immutability constraint).
- Acceptance criteria: Given an admin updates a setting, when the change is saved,
  then the system should write one audit entry with the before/after values.
- Non-functional: the audit log must sustain 1000 writes per second.

Out of scope

- Log analytics dashboards are excluded.
""",
)

_PLATFORM_RATELIMIT = TestCase(
    name="api-rate-limit",
    bu="Platform",
    task="Add per-tenant API rate limiting",
    prd="""
Overview

Generally speaking, the API is being abused by a small number of tenants. This
overview restates that context at length.

Requirements

- The system must enforce a configurable per-tenant request rate limit.
- Requests over the limit must receive a 429 response with a Retry-After header.
- Rate-limit counters must be consistent across multiple API server instances.
- Acceptance criteria: Given a tenant over its limit, when it sends a request,
  then the system should reject it with 429.
- Performance: the limiter must add no more than 5ms of latency.
- Depends on the shared Redis cache.
""",
)

_PLATFORM_FEATUREFLAG = TestCase(
    name="feature-flags",
    bu="Platform",
    task="Add a feature-flag service with gradual rollout",
    prd="""
Introduction

This introduction is intentionally verbose and, essentially, repeats the
motivation for feature flags several times over.

Requirements

- The system must let operators toggle features per environment.
- Flags must support percentage-based gradual rollout to users.
- Flag evaluation must be consistent for a given user (sticky bucketing).
- Acceptance criteria: Given a flag at 50% rollout, when the same user is
  evaluated twice, then the system should return the same result both times.
- Non-functional: flag evaluation must not exceed 1ms.

Out of scope

- A visual flag-management UI is not in scope.
""",
)


def sample_cases() -> list[TestCase]:
    """Return the full 8-case, 2-BU validation suite."""
    return [
        _PAYMENTS_CHECKOUT,
        _PAYMENTS_FRAUD,
        _PAYMENTS_WALLET,
        _PAYMENTS_PAYOUT,
        _PLATFORM_SSO,
        _PLATFORM_AUDIT,
        _PLATFORM_RATELIMIT,
        _PLATFORM_FEATUREFLAG,
    ]
