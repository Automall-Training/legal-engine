# Example requests

Invented firms only. Each line: the request → what the module does.

- "Можно ли нашей ООО в Молдове продавать онлайн-курсы физлицам в Румынии без регистрации там?" → answer: regime
  per `jurisdiction.md` (consumer rules of the buyer's country, VAT place of supply), cards for the acts cited,
  lawful path (what to show at checkout, which registration if any), risk table.
- "Este în vigoare art. 1166 din Codul civil al României în redacția pe care o citez?" → version check: one card,
  `scope: full`, result and sources block; no answer document.
- "Какой штраф в Молдове за сайт без политики конфиденциальности?" → the privacy module is on → it answers and
  asks this module for the version check of the cited acts; the module is off → back to the router: say the
  privacy module is off and offer to turn it on; this module does not answer it.
- "Is a supplier in Romania allowed to change prices in a signed B2B contract?" → answer with the contract
  question kept general; a review of the actual contract goes to `legal-contracts`.
- "Проверь, не поменялся ли закон, на который ссылается наш договор" → version check for the cited acts; the
  re-review of the contract itself is `legal-contracts` (and, from step 9, `legal-watch`).
