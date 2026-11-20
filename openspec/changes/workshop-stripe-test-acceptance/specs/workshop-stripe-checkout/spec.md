# Workshop Stripe Checkout

## Purpose

Let an authorized tester purchase a Workshop vehicle scope with Stripe TEST
and receive access only from a verified server-side settlement.

## ADDED Requirements

### Requirement: TEST configuration and purchase notice
The Workshop SHALL identify an active TEST checkout and present its price and
purchase notices before accepting the customer's terms confirmation.

#### Scenario: Eligible tester at an approved TEST origin
- **WHEN** TEST purchasing is confirmed and the required purchase notices are available
- **THEN** Workshop identifies the flow as TEST and displays the configured one-time USD 20 price and notices
- **AND** a tester who confirms the terms and submits can open hosted TEST Checkout

#### Scenario: Missing or mismatched TEST configuration
- **WHEN** the merchant, Price, origin, notices, or requested payment mode cannot be verified
- **THEN** the server rejects new checkout without exposing credentials or creating an entitlement

### Requirement: Server-verified access
Workshop SHALL grant access once per verified payment to the authenticated
purchaser for the order's canonical vehicle configuration and region.

#### Scenario: Confirmed payment and repeated event
- **WHEN** Stripe delivers a valid TEST settlement for the stored order and later repeats it
- **THEN** the purchaser receives one grant for the purchased configuration and region
- **AND** refreshing order status or replaying the event cannot create another grant or charge

#### Scenario: Checkout return while the order is pending
- **WHEN** the tester returns from Checkout before settlement is verified
- **THEN** Workshop shows the order state while withholding paid article access

#### Scenario: Canceled checkout
- **WHEN** Checkout is canceled or expires without settlement
- **THEN** the tester receives no paid access
- **AND** a fresh purchase requires an explicit action after the server confirms that retry is safe
