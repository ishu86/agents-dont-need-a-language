# Feature: loyalty points

We want to reward purchases with loyalty points. Add a method on the shop object:

`shop.points(customerId: string): number | undefined`

It returns the customer's current points balance (0 for a new customer, `undefined` for an unknown id).

Rules:
- When an order is paid at checkout, the customer earns `floor(order total in cents / 100)` points multiplied by their VIP tier multiplier: **gold members earn double (x2), every other tier x1**. The tier that counts is the one the customer had *before* this order was paid (an order that lifts someone into gold does not itself earn double).
- When a refund is issued (full, partial, or as part of any flow that refunds), points are taken back: `floor(refunded amount in cents / 100)` times the same multiplier that applied when the order was paid (not the customer's current tier). The balance never goes below 0.
- Failed checkouts earn nothing.

Example: Alice pays an order of total 2378 -> 23 points. Refunding one mug (864 cents) takes back 8 points (15 left); refunding the rest (1514 cents) takes back 15 (0 left).
