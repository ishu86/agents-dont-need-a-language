import { state } from "../state.ts";
import { percentOf } from "../money.ts";
import { registerRule } from "../pricing.ts";

registerRule("bulk", ({ lines }: any) => {
  let total = 0;
  for (const line of lines) {
    if (line.qty >= state.config.bulkQty) total += percentOf(line.lineCents, state.config.bulkBps);
  }
  return total;
});
