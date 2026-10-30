# Partial refunds leave no trail in the audit log

Our finance team reconciles refunds against the audit log. Refunds that return the whole order show up there, but when only some items are refunded, nothing is recorded: the money has gone out, the customer got the "refund issued" email, but the audit log has no entry. Every refund, partial or full, must add one "refund" entry for the order whose detail is the refunded amount in cents.

Repro: Alice buys 2 mugs (order total 2378) and we refund 1 mug (864 cents), then the remainder (1514 cents). The audit log should hold two refund entries for the order, "864" then "1514"; it only has the second.
