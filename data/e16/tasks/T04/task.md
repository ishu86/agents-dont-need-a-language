# Partial refunds don't put the items back in stock

When we refund only some of the units in an order, the refund money goes out and the order is marked as partially refunded, but the returned units never show up in the inventory count. Example: Alice buys 2 mugs (stock goes 20 -> 18), we refund 1 mug, and stock should read 19; it still says 18. Refunding the whole order at once does restore stock correctly, and so does refunding the last remaining unit afterwards... but only that last unit comes back, so the books stay short by the units from the earlier partial refunds.
