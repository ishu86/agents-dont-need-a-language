// Public API of shopcore. Builds a Ctx and the rule registry once, then exposes methods that thread them explicitly.
import type {
  AuditEntry, Clock, Config, Coupon, Customer, Cents, Ctx, EmailMessage, Order, Product, Result,
} from "./types.ts";
import { makeConfig } from "./config.ts";
import { createDb, createLog } from "./storage.ts";
import { addProduct, getProduct, listProducts, type ProductInput } from "./catalog.ts";
import { addStock, stockOf } from "./inventory.ts";
import { addCustomer, getCustomer, tierOf, type CustomerInput } from "./customers.ts";
import { addCoupon, defaultRules, type CouponInput, type RuleRegistry } from "./pricing.ts";
import { addItem, applyCoupon, checkout, createOrder, getOrder, type CreateOrderInput } from "./orders.ts";
import { refund, type RefundResult } from "./refunds.ts";
import { listOutbox } from "./notifications.ts";
import { entries } from "./audit.ts";
import type { StockLine } from "./inventory.ts";

export interface ShopOptions {
  config?: Partial<Config>;
  now?: () => number;
  rules?: RuleRegistry;
}

export function createShop(options: ShopOptions = {}) {
  const clock: Clock = { now: options.now ?? (() => Date.now()) };
  const ctx: Ctx = {
    db: createDb(),
    config: makeConfig(options.config),
    clock,
    log: createLog(),
  };
  const rules: RuleRegistry = options.rules ?? defaultRules();

  return {
    addProduct: (input: ProductInput): Result<Product> => addProduct(ctx.db, input),
    addStock: (sku: string, qty: number): Result<number> => addStock(ctx, sku, qty),
    addCustomer: (input: CustomerInput): Result<Customer> => addCustomer(ctx, input),
    addCoupon: (input: CouponInput): Result<Coupon> => addCoupon(ctx.db, input),
    createOrder: (input: CreateOrderInput): Result<Order> => createOrder(ctx, input),
    addItem: (orderId: string, sku: string, qty: number): Result<Order> => addItem(ctx, rules, orderId, sku, qty),
    applyCoupon: (orderId: string, code: string): Result<Order> => applyCoupon(ctx, rules, orderId, code),
    checkout: (orderId: string): Result<Order> => checkout(ctx, rules, orderId),
    refund: (orderId: string, lines?: StockLine[]): Result<RefundResult> => refund(ctx, orderId, lines),
    getOrder: (orderId: string): Order | undefined => getOrder(ctx.db, orderId),
    getProduct: (sku: string): Product | undefined => getProduct(ctx.db, sku),
    listProducts: (): Product[] => listProducts(ctx.db),
    getCustomer: (id: string): Customer | undefined => getCustomer(ctx.db, id),
    /** Name of the customer's current VIP tier, e.g. "none", "silver", "gold". */
    tier: (customerId: string): string | undefined => {
      const c = getCustomer(ctx.db, customerId);
      return c ? tierOf(ctx.config, c).name : undefined;
    },
    stock: (sku: string): number => stockOf(ctx.db, sku),
    outbox: (): EmailMessage[] => listOutbox(ctx.db),
    audit: (): AuditEntry[] => entries(ctx.log),
  };
}

export type Shop = ReturnType<typeof createShop>;
export type { Cents };
