# Feature: tax-exempt customers

Some of our customers (charities, resellers) don't pay sales tax. Add a method on the shop object:

`shop.setTaxExempt(customerId: string, exempt: boolean): Result<Customer>`

It flags or unflags the customer and returns the updated customer, which has a boolean `taxExempt` field (false for every customer by default). Unknown ids fail with error code `"not_found"`.

- For a tax-exempt customer, the tax on their orders is 0 regardless of region. Everything else (discounts, shipping, totals aside from tax) is unchanged.
- The flag applies to every order at the moment it is priced, including orders that were created and filled before the flag was set: the checkout total and anything charged or refunded afterwards must reflect the customer's status at checkout. Unflagging restores normal tax.
- Each call adds an audit entry with action `"tax_exempt_set"`, subject = the customer id, detail `"true"` or `"false"`.

Example: Bob (region NY) has one lamp (4000 cents) in an open order. After `setTaxExempt("bob", true)`, checking it out costs 4000 + 800 shipping = 4800 (instead of 4960).
