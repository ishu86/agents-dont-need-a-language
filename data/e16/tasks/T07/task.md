# Feature: cancel an order

Support needs a way to cancel an order. Add a method on the shop object:

`shop.cancelOrder(orderId: string): Result<Order>`

where the result follows the same ok/error shape as the other methods and the returned order has `status: "cancelled"`.

- An **open** order (not yet paid) is simply cancelled. Stock is untouched.
- A **paid** or **partially refunded** order is cancelled by refunding everything that has not been refunded yet, exactly as a normal full refund would: stock for the remaining units goes back, the customer's lifetime spend drops, a refund is audited and a "refund_issued" email is queued. The order's `refundedCents` ends up equal to what the customer originally paid.
- Every successful cancellation adds an audit entry with action `"order_cancelled"` (subject = the order id), and queues an email to the customer with template `"order_cancelled"`. For a paid order the order of events is: refund audit entry, refund email, then the cancellation audit entry and cancellation email.
- Orders that are already refunded or cancelled fail with error code `"bad_state"`; unknown ids fail with `"not_found"`. A cancelled order cannot be checked out, edited, or refunded (`"bad_state"`).
