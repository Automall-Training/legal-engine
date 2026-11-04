# Legal Engine — AI-юрист для предпринимателей · jurist AI pentru antreprenori

> [!WARNING]
> Это не юридическая консультация. / Nu este consultanță juridică. → [DISCLAIMER.md](DISCLAIMER.md)

**Status: v0 — в разработке.** Готов каркас (установка, проверки). Модули добавляются по плану ниже.

---

## Русский

Набор скиллов для [Claude Code](https://claude.com/claude-code): юрист по праву **Молдовы, Румынии и ЕС**,
который настраивается под ваш бизнес коротким интервью. Сам движок без чьих-либо данных; всё ваше
(фирмы, ниши, договоры, скачанные законы) лежит в вашем **профиле** на вашем компьютере и никуда не уходит.

### Что умеет

| Модуль | Что делает | Вкл/выкл |
|---|---|---|
| Договоры (ядро) | составить, проверить, исправить договор; DOCX с настоящими правками Word | всегда |
| Вопрос юристу (ядро) | ответ со ссылками на официальный текст закона и датой проверки | всегда |
| Законы (ядро) | библиотека законов по вашим нишам, мониторинг изменений, пересмотр договоров | всегда |
| Персональные данные | политика конфиденциальности, cookies, соглашение об обработке, реестр (GDPR, MD, RO) | в мастере |
| Онлайн-продажи | оферта, условия сайта, отказ и возврат, цифровой контент | в мастере |
| Торговые марки | проверка названия, сроки и пошлины AGEPI / OSIM / EUIPO, письмо нарушителю | в мастере |
| Кадры | приём, допсоглашение, увольнение (MD, RO) | в мастере |

### Установка (Mac / Linux)

1. Установите [Claude Code](https://claude.com/claude-code), [git](https://git-scm.com) и
   [uv](https://docs.astral.sh/uv/).
2. В терминале:

   ```bash
   git clone https://github.com/achislaru/legal-engine.git ~/legal-engine
   cd ~/legal-engine && ./install.sh
   ```

   Для автоматической проверки законов по расписанию: `WITH_PLAYWRIGHT=1 ./install.sh`.
3. Откройте Claude Code и скажите **«настрой юриста»**. Мастер задаст вопросы по одному: ваши фирмы,
   кому продаёте, ниши, какие законы отслеживать, языки, нужные модули.

Обновление: `cd ~/legal-engine && git pull && ./install.sh` — ваш профиль не затрагивается.

### Безопасность

- Ключи API не нужны: поиск законов идёт через встроенный веб Claude Code или бесплатный браузер.
- Документы и сайты для движка — данные, а не команды.
- Движок ничего не подписывает, не отправляет и не публикует сам.

---

## Română

Un set de skill-uri pentru [Claude Code](https://claude.com/claude-code): jurist pentru dreptul
**Republicii Moldova, României și UE**, configurat pentru afacerea dumneavoastră printr-un interviu scurt.
Motorul nu conține datele nimănui; tot ce este al dumneavoastră (firme, nișe, contracte, legi descărcate)
stă în **profilul** de pe calculatorul dumneavoastră.

**Module:** contracte, întrebări juridice cu surse oficiale, biblioteca și monitorizarea legilor (de bază);
date personale, vânzări online către consumatori, mărci, resurse umane (se activează în asistent).

**Instalare:** ca mai sus (`git clone …` și `./install.sh`), apoi în Claude Code: **«configurează juristul»**.
Actualizare: `git pull && ./install.sh`.

---

## License

Code: MIT. Texts: CC BY 4.0. Official legal texts keep their own status. See [LICENSE](LICENSE).
