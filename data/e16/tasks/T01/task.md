# Silver members get a discount stacked on top of "exclusive" coupons

We sell some coupons as exclusive: when a coupon is created with `stackable: false`, the customer is supposed to get the coupon discount *instead of* their membership (VIP) discount, not on top of it. Stackable coupons should still combine with the membership discount as before.

Repro: a silver-tier customer (Alice) puts 2 lamps (4000 cents each) in an order and applies a 10% coupon (`value: 1000`, `stackable: false`). She should pay 800 cents off in total (just the coupon), for a final total of 7776. Instead the order shows both a membership discount and a coupon discount, and the total comes out lower than that.
