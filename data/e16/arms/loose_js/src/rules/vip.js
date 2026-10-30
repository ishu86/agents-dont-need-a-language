import { percentOf } from "../money.js";
import { getCoupon, registerRule } from "../pricing.js";

registerRule("vip", ({ order, tier, remaining }) => {
  const coupon = getCoupon(order.couponCode);
  if (coupon && !coupon.stackable) return 0;
  return percentOf(remaining, tier.discountBps);
});
