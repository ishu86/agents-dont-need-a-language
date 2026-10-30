import { state } from "../state.js";
import { percentOf } from "../money.js";
import { registerRule } from "../pricing.js";

registerRule("bulk", ({ lines }) => {
  let total = 0;
  for (const line of lines) {
    if (line.qty >= state.config.bulkQty) total += percentOf(line.lineCents, state.config.bulkBps);
  }
  return total;
});
