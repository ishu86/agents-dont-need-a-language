import { percentOf } from "../money.ts";
import { getCoupon, registerRule } from "../pricing.ts";

registerRule("coupon", ({ order, remaining }: any) => {
  const coupon = getCoupon(order.couponCode);
  if (!coupon) return 0;
  if (coupon.kind === "percent") return percentOf(remaining, coupon.value);
  return Math.min(coupon.value, remaining);
});
