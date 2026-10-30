# Sales tax charged for the wrong state when shipping to a different region

When an order is created with a `shipRegion` that differs from the customer's own region, the tax on the order should be the rate for the region it ships to. We have a New York customer (Bob, region "NY") sending a gift to California: one lamp (4000 cents) with `shipRegion: "CA"` should carry 320 cents of tax (8%), making the order total 5120 including shipping. Instead the order shows 160 cents of tax (the New York rate) and a total of 4960, and the customer is charged that at checkout too.
