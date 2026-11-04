# Example requests

Say it in plain words (the router picks `legal-contracts`) or call `/legal-workflow`. Parties below are invented.

## Draft

«Составь договор услуг между двумя молдавскими SRL в интересах исполнителя. Право Молдовы согласовано. Предмет и
цена в приложении. Поясняй по-русски, договор по-румынски, результат DOCX. Незаполненные реквизиты оставь полями.»

## Audit

«Проверь приложенный румынский договор поставки в интересах покупателя. Анализ на 15.06.2024; отдельно покажи, что
изменить для исполнения сейчас. Оригинал не редактируй. Нужны замечания по пунктам, источники и формулировки.»

## Edit

«Внеси в DOCX согласованные изменения из списка. Цену и распределение IP не меняй. Дай настоящие правки Word,
чистовую версию и объяснение существенных изменений.»

## Romanian conversation

„Verifică acest acord de confidențialitate pentru o societate din România. Explică riscurile și propune clauze în
română. Dacă nu poți confirma forma aplicabilă a unei norme, indică exact limita verificării.”

## English conversation

“Review this Romanian services agreement for the supplier. Explain your findings in English and keep proposed
clauses in Romanian. Give me real Word tracked changes plus a clean copy if edits are needed.”

## Switching language

After an audit in Russian: “Please continue in English. Keep the contract in Romanian.”

## Contract with data

«Молдавский SaaS (Example Soft SRL) обслуживает румынского клиента; используются email сотрудников. Подготовь
договор услуг.» → the data clause is drafted here; whether a separate DPA and transfer terms are needed is a
question for the `privacy` module (if it is on), with conditional options until the facts are known.
