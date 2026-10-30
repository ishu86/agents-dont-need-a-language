# Single-use coupon is lost when checkout fails for lack of stock

A customer used our single-use coupon (`maxUses: 1`) on an order, but the checkout was rejected because an item was out of stock. After we restocked the item, retrying the checkout for the same order is refused with a "coupon exhausted" error, even though the customer never actually got to use the coupon. A coupon should only be consumed by a checkout that succeeds. (Once a checkout with it succeeds, nobody else may use it again, as before.)

Repro: coupon `ONE` fixed 100 cents, maxUses 1. Alice's order: 25 pens (only 20 in stock) with `ONE` applied. Checkout fails with out_of_stock. Add 10 pens of stock. Checkout should now succeed.
