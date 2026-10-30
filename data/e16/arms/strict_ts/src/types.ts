// Shared types for shopcore. All money is integer cents.

export type Cents = number;

export type ErrorCode =
  | "not_found"
  | "invalid"
  | "duplicate"
  | "out_of_stock"
  | "coupon_invalid"
  | "coupon_expired"
  | "coupon_exhausted"
  | "bad_state";

export interface ShopError {
  code: ErrorCode;
  message: string;
}

export type Result<T, E = ShopError> =
  | { ok: true; value: T }
  | { ok: false; error: E };

export function ok<T>(value: T): Result<T, never> {
  return { ok: true, value };
}

export function err(code: ErrorCode, message: string): Result<never, ShopError> {
  return { ok: false, error: { code, message } };
}

// ---- domain ----

export interface Product {
  sku: string;
  name: string;
  priceCents: Cents;
  weightG: number;
  taxable: boolean;
  category: string;
}

export interface Customer {
  id: string;
  name: string;
  email: string;
  region: string;
  lifetimeSpendCents: Cents;
}

export interface VipTier {
  name: string;
  minSpendCents: Cents;
  discountBps: number;
  freeShipping: boolean;
}

export interface Coupon {
  code: string;
  kind: "percent" | "fixed";
  /** basis points for "percent", cents for "fixed" */
  value: number;
  /** false: the coupon replaces the VIP discount instead of stacking with it */
  stackable: boolean;
  minSubtotalCents: Cents;
  maxUses: number | null;
  expiresAt: number | null;
}

export interface OrderItem {
  sku: string;
  qty: number;
  unitPriceCents: Cents;
}

export type OrderStatus = "open" | "paid" | "partially_refunded" | "refunded";

export interface DiscountLine {
  rule: string;
  amountCents: Cents;
}

export interface Pricing {
  subtotalCents: Cents;
  discounts: DiscountLine[];
  discountCents: Cents;
  taxableCents: Cents;
  taxCents: Cents;
  shippingCents: Cents;
  totalCents: Cents;
}

export interface Order {
  id: string;
  customerId: string;
  shipRegion: string;
  items: OrderItem[];
  couponCode: string | null;
  status: OrderStatus;
  pricing: Pricing;
  /** goods share (after discount, with tax) of each line, set at checkout */
  lineNetCents: Record<string, Cents>;
  refundedByLine: Record<string, { qty: number; cents: Cents }>;
  refundedCents: Cents;
  createdAt: number;
  paidAt: number | null;
}

export type EmailTemplate = "order_confirmation" | "refund_issued";

export interface EmailMessage {
  to: string;
  subject: string;
  template: EmailTemplate;
  orderId: string;
  at: number;
}

export interface AuditEntry {
  at: number;
  action: string;
  subjectId: string;
  detail: string;
}

// ---- infrastructure ----

export interface Config {
  defaultRegion: string;
  taxBpsByRegion: Record<string, number>;
  shippingBaseCents: Cents;
  shippingPerKgCents: Cents;
  freeShippingThresholdCents: Cents;
  bulkQty: number;
  bulkBps: number;
  /** ascending by minSpendCents; first entry is the base tier */
  vipTiers: VipTier[];
}

export interface Clock {
  now(): number;
}

export interface Db {
  products: Map<string, Product>;
  stock: Map<string, number>;
  customers: Map<string, Customer>;
  coupons: Map<string, Coupon>;
  couponUses: Map<string, number>;
  orders: Map<string, Order>;
  outbox: EmailMessage[];
  seq: number;
}

export interface AuditLog {
  entries: AuditEntry[];
}

/** Everything a function may touch is reachable from here; nothing is global. */
export interface Ctx {
  db: Db;
  config: Config;
  clock: Clock;
  log: AuditLog;
}
