# Free shipping is granted even after a coupon brings the order below the threshold

Orders get free shipping when the amount the customer actually pays for goods (after discounts) reaches 5000 cents. We are seeing orders that qualify only because of the pre-discount price. Example: Alice orders one lamp (4000) and one book (1500), subtotal 5500, and applies a fixed coupon of 1000 cents. Goods are now 4500, so shipping should be charged (800 cents for the 1.9 kg parcel) and the total should be 5562. The order currently shows 0 shipping and a total of 4762.

Reaching the threshold exactly still means free shipping (a 500-cent coupon on the same basket gives goods of exactly 5000 and a total of 5291).
