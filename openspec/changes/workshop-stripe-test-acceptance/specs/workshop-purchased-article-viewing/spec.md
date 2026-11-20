# Workshop purchased article viewing

## Purpose

Let purchasers find and reopen Workshop articles for the exact vehicle scope
they own, with clear states while payment or content is pending.

## ADDED Requirements

### Requirement: Navigation to an owned article
Workshop SHALL preserve the selected configuration and region as an
authenticated owner moves from the confirmed order or Library to the
corresponding article.

#### Scenario: Paid order with an available article
- **WHEN** the owner returns after settlement and opens an article for the purchased scope
- **THEN** Workshop renders the authorized article and available illustrations
- **AND** the owner can reload the article or reopen it from Library without another checkout

#### Scenario: Article preparation is still in progress
- **WHEN** payment is verified but the requested article is not ready
- **THEN** Workshop distinguishes preparation from payment, preserves the purchase and exposes a recovery path

### Requirement: Article and media are scoped to ownership
Workshop SHALL enforce article and media access for the signed-in owner and
exact purchased vehicle configuration and region on server reads.

#### Scenario: Unowned scope or different account
- **WHEN** a different account, vehicle configuration, region, or signed-out browser requests the protected article or media
- **THEN** Workshop withholds the protected content and shows an appropriate access state

#### Scenario: Revoked purchase
- **WHEN** the server verifies a full refund that revokes access
- **THEN** subsequent protected article and media reads are denied
