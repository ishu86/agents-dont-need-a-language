import { percentOf } from "../money.ts";
import { getCoupon, registerRule } from "../pricing.ts";

registerRule("vip", ({ order, tier, remaining }: any) => {
  const coupon = getCoupon(order.couponCode);
  if (coupon && !coupon.stackable) return 0;
  return percentOf(remaining, tier.discountBps);
});
