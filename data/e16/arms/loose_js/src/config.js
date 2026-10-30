export function defaultConfig() {
  return {
    defaultRegion: "CA",
    taxBpsByRegion: { CA: 800, NY: 400, OR: 0, DE: 1900 },
    shippingBaseCents: 500,
    shippingPerKgCents: 150,
    freeShippingThresholdCents: 5000,
    bulkQty: 10,
    bulkBps: 1000,
    vipTiers: [
      { name: "none", minSpendCents: 0, discountBps: 0, freeShipping: false },
      { name: "silver", minSpendCents: 20000, discountBps: 500, freeShipping: false },
      { name: "gold", minSpendCents: 100000, discountBps: 1000, freeShipping: true },
    ],
  };
}

// Overrides replace top-level fields wholesale.
export function makeConfig(overrides) {
  return Object.assign(defaultConfig(), overrides);
}
