# Generation 2 Decision-Grade Accounting Contract

Date: 2026-09-22

Status: **FROZEN BEFORE GENERATION-2 CAMPAIGN EXECUTION**

Target methodology:

`UNADJUSTED_EXECUTION_WITH_CORPORATE_ACTIONS-v1`

This contract is the successor to research-only QFQ comparability accounting.
It must be implemented and rehearsed on research/synthetic data before any new
final-holdout access.

## Price basis

- Signals may use a separately declared research signal series.
- Executions and portfolio marks use unadjusted market prices.
- Same-bar execution is forbidden.
- A completed-session signal may execute no earlier than the next eligible
  session open.
- No hidden QFQ adjustment may be applied to execution prices, quantities, or
  cash.

## Portfolio ledger

The canonical portfolio ledger must explicitly track:

- cash;
- shares per symbol;
- pending orders;
- fills;
- friction;
- dividend receivables;
- split/share adjustments;
- total equity;
- source/event identities.

Every state transition must be deterministic and reproducible from the sealed
inputs.

## Splits

For a valid split event:

- event identity and effective/ex-date must come from sealed corporate-action
  evidence;
- share quantity is multiplied by the split ratio before the first market
  session on which the post-split shares/prices apply;
- cash is unchanged except for explicitly sourced cash-in-lieu events;
- ambiguous ratio/date/order of application => UNKNOWN/ABSTAIN.

Reverse splits use the same rule.

Fractional-share handling must be explicit. Until a broker-specific rule is
preregistered, fractional shares remain in the research ledger rather than
inventing cash-in-lieu.

## Cash distributions

For cash dividends/distributions:

- entitlement is based on the shares held at the close immediately preceding
  the ex-date;
- a receivable is created on the ex-date;
- the receivable remains part of portfolio equity until paid;
- cash is credited on the authoritative pay date;
- the receivable is reduced by the identical amount on payment;
- multiple legitimate distribution components are recorded separately and may
  be aggregated only after their identities are preserved;
- missing or ambiguous ex-date/pay-date/amount evidence => UNKNOWN/ABSTAIN.

Gross cash distributions are used unless a separately preregistered tax or
withholding model exists.

## Evaluation-window boundaries

Corporate-action entitlement is not discarded merely because payment occurs
after the scored-window end.

If a position becomes entitled before the window end but payment occurs later,
the receivable is included in terminal equity. No future price data is required
to value a fixed cash receivable.

Pre-window corporate actions may be used only to establish valid starting
shares/cash/warmup state and may not contribute scored performance.

## Friction

- initial cash: 100000;
- primary friction: 3 bps;
- required cases: 0, 3, 10, 25, 50 bps;
- friction applies to absolute traded notional on buys and sells;
- buys are cash-constrained after friction;
- corporate-action share/cash adjustments do not themselves incur trading
  friction.

## Invariants

Every replay must verify:

- cash finite;
- shares finite and non-negative;
- no leverage;
- no short positions;
- no fill before its eligible session;
- no duplicated corporate-action application;
- receivable conservation;
- split quantity conservation;
- equity identity:
  cash + market value of shares + receivables;
- deterministic replay identity.

Any invariant failure => UNKNOWN/ABSTAIN.

## Source requirements

Corporate-action evidence must be sealed and content-addressed before replay.

For every event used by the ledger, preserve at minimum:

- symbol;
- event type;
- ex/effective date;
- pay date when relevant;
- amount or ratio;
- provider/source;
- raw-record identity/hash;
- normalized-event identity/hash.

If two permitted sources disagree on a decision-critical field, do not choose
the value that improves performance. Reconcile independently or ABSTAIN.

## Required tests before real holdout

- forward split;
- reverse split;
- ordinary cash dividend;
- multiple distribution components on one ex-date;
- ex-date inside/pay-date outside evaluation window;
- missing pay date;
- duplicate provider event;
- conflicting provider event;
- interrupted replay and deterministic restart;
- friction around corporate-action dates;
- next-session timing/no-lookahead;
- exact accounting conservation.

No real final-holdout access is authorized until these tests and the complete
synthetic pipeline rehearsal pass.
