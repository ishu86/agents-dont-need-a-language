# Feature: clearance discount

Products in the category `"clearance"` should automatically get 20% off. No new method is needed; it must show up in the order's pricing like the other automatic discounts.

- The discount is named `"clearance"` in the order's `pricing.discounts`, and equals 20% of the **undiscounted value of each clearance line** (unit price x quantity), rounded to the nearest cent, summed over all clearance lines. Lines of other categories are not affected.
- It is applied **after the bulk discount and before the VIP and coupon discounts**, so the VIP and coupon discounts are computed on what is left after it. The discount order matters for totals.
- It counts as a normal discount for everything else (tax is on the discounted amount, free shipping is judged on the discounted goods value, etc.).

Examples (default prices; "oldmug" is a 1000-cent clearance product, 300 g, taxable):
- Alice (no tier, CA 8% tax) orders 1 oldmug: discount 200, goods 800, tax 64, shipping 650 -> total 1514.
- Carol (silver, region OR, no tax) orders 1 oldmug: clearance 200, then silver 5% of the remaining 800 = 40 -> goods 760, shipping 650 -> total 1410.
- Alice orders 10 oldmugs: bulk 1000 and clearance 2000 (20% of the full 10000) -> goods 7000, tax 560, free shipping -> total 7560.
