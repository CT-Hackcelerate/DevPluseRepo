"""Sample PRDs from two Business Units — the A/B validation dataset.

Eight feature-request PRDs, deliberately verbose the way real PRDs are: each
carries pages of framing — executive summaries, background, motivation,
stakeholder lists, revision history, and appendices — wrapped around a small
core of decision-relevant requirements. That framing is exactly what
``compress_prd`` strips, so the suite demonstrates the ~67% input reduction on
realistic input rather than on already-terse bullet lists.

Split across two BUs (Payments and Platform). Each pairs a raw PRD with the
concrete task the AI is asked to plan. These drive ``run_ab_suite`` to
demonstrate the cost/quality claims without any external systems.
"""

from __future__ import annotations

from .ab_runner import TestCase

# ── Framing generator ────────────────────────────────────────────────────────
#
# Real PRDs bury a handful of requirements inside a lot of narrative. This helper
# reproduces that shape: several paragraphs of context that carry no *decision*
# (and are therefore dropped by the compressor), wrapped around the requirement
# core. The prose is deliberately free of requirement cue words so the compressor
# classifies it as low-signal framing and drops it — mirroring how it treats a
# real exec summary or background section.


def _framing(topic: str) -> str:
    """Return several paragraphs of cue-free PRD boilerplate about ``topic``."""
    return f"""Executive Summary

This document has been prepared by the product organisation to capture the broad
narrative around {topic}. Much of the material here restates historical context
from earlier quarters and prior planning cycles. The early sections are
intentionally thorough. Readers already familiar with the domain may wish to skim
past them and jump ahead to the later portions.

Background

For a long time, many teams have discussed {topic} at length across numerous
internal forums. Countless meetings, retrospectives, and hallway conversations
have circled back to it. This section rehashes that discussion so future readers
inherit the full picture, even though little of the framing here changes from one
week to the next.

Motivation

The wider motivation traces back to feedback gathered from partners and from the
field over several review cycles. Sentiment has been broadly consistent, and the
themes echo what earlier documents already captured at length. None of this is
new, but it is repeated here for completeness and for the benefit of newcomers.

Stakeholders

The primary reviewers include the product lead, the engineering manager, the
design partner, and a rotating cast from the wider guild. Their names and roles
are recorded in the tracker rather than repeated here.

Revision History

The first draft landed last quarter. The second folded in comments from the
review forum. This third pass mostly tidies wording and reorganises the framing
paragraphs.

Appendix

Additional references, links to older decks, and a short glossary of house
terminology are collected at the very end for the curious reader.
"""


def _prd(topic: str, requirements: str) -> str:
    """Assemble a verbose PRD: heavy framing + the requirement core."""
    return _framing(topic) + "\n" + requirements.strip() + "\n"


# ── BU 1: Payments ───────────────────────────────────────────────────────────

_PAYMENTS_CHECKOUT = TestCase(
    name="checkout-retry",
    bu="Payments",
    task="Implement automatic retry with idempotency for failed checkout charges",
    prd=_prd(
        "checkout charge reliability",
        """
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
    ),
)

_PAYMENTS_FRAUD = TestCase(
    name="fraud-scoring",
    bu="Payments",
    task="Add a real-time fraud risk score to each transaction",
    prd=_prd(
        "real-time fraud scoring",
        """
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
    ),
)

_PAYMENTS_WALLET = TestCase(
    name="wallet-topup",
    bu="Payments",
    task="Add a stored-value wallet with top-up",
    prd=_prd(
        "the stored-value wallet",
        """
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
    ),
)

_PAYMENTS_PAYOUT = TestCase(
    name="scheduled-payout",
    bu="Payments",
    task="Support scheduled payouts to merchants",
    prd=_prd(
        "scheduled merchant payouts",
        """
Requirements

- The system must support daily and weekly scheduled payouts to merchants.
- Payouts must be idempotent to avoid double-paying a merchant.
- A payout must not be issued if the merchant account is under review.
- Acceptance criteria: Given a scheduled weekly payout, when the schedule fires,
  then the system should create exactly one payout for the period.
- Depends on the existing Ledger service and the BankTransfer integration.
""",
    ),
)

# ── BU 2: Platform ───────────────────────────────────────────────────────────

_PLATFORM_SSO = TestCase(
    name="sso-login",
    bu="Platform",
    task="Add SSO login via SAML",
    prd=_prd(
        "single sign-on",
        """
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
    ),
)

_PLATFORM_AUDIT = TestCase(
    name="audit-log",
    bu="Platform",
    task="Add an immutable audit log for admin actions",
    prd=_prd(
        "the admin audit trail",
        """
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
    ),
)

_PLATFORM_RATELIMIT = TestCase(
    name="api-rate-limit",
    bu="Platform",
    task="Add per-tenant API rate limiting",
    prd=_prd(
        "per-tenant rate limiting",
        """
Requirements

- The system must enforce a configurable per-tenant request rate limit.
- Requests over the limit must receive a 429 response with a Retry-After header.
- Rate-limit counters must be consistent across multiple API server instances.
- Acceptance criteria: Given a tenant over its limit, when it sends a request,
  then the system should reject it with 429.
- Performance: the limiter must add no more than 5ms of latency.
- Depends on the shared Redis cache.
""",
    ),
)

_PLATFORM_FEATUREFLAG = TestCase(
    name="feature-flags",
    bu="Platform",
    task="Add a feature-flag service with gradual rollout",
    prd=_prd(
        "the feature-flag service",
        """
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
    ),
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
