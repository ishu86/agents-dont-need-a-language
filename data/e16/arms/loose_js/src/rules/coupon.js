import { percentOf } from "../money.js";
import { getCoupon, registerRule } from "../pricing.js";

registerRule("coupon", ({ order, remaining }) => {
  const coupon = getCoupon(order.couponCode);
  if (!coupon) return 0;
  if (coupon.kind === "percent") return percentOf(remaining, coupon.value);
  return Math.min(coupon.value, remaining);
});
