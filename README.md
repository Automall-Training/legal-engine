# Legal Engine — AI-юрист для предпринимателей · jurist AI pentru antreprenori

> [!WARNING]
> Это не юридическая консультация. / Nu este consultanță juridică. → [DISCLAIMER.md](DISCLAIMER.md)

**Status: v1.1.0.** Все модули ниже готовы. Известные ограничения (например, часть официальных сайтов закрыта для
автоматического чтения) — в [docs/STATUS.md](docs/STATUS.md). / Toate modulele sunt gata; limitele cunoscute — în
[docs/STATUS.md](docs/STATUS.md).

---

## Русский

Набор скиллов для [Claude Code](https://claude.com/claude-code): юрист по праву **Молдовы, Румынии и ЕС**,
который настраивается под ваш бизнес коротким интервью. Сам движок без чьих-либо данных; всё ваше
(фирмы, ниши, договоры, скачанные законы) хранится в вашем **профиле** на вашем компьютере и никогда не попадает
в этот репозиторий. То, что вы пишете в разговоре, и документы, которые читает агент, обрабатывает выбранный вами
AI-сервис (например, Claude) по условиям его поставщика.

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
   git clone https://github.com/Automall-Training/legal-engine.git ~/legal-engine
   cd ~/legal-engine && ./install.sh
   ```

   Для автоматической проверки законов по расписанию: `WITH_PLAYWRIGHT=1 ./install.sh`.
3. Откройте Claude Code и скажите **«настрой юриста»**. Мастер задаст вопросы по одному: ваши фирмы,
   кому продаёте, ниши, какие законы отслеживать, языки, нужные модули.

Обновление: `cd ~/legal-engine && git pull && ./install.sh` — ваш профиль не затрагивается.

### Установка в Codex (Mac)

Тот же движок работает в Codex. Скиллы кладутся в папку скиллов Codex:

```
git clone https://github.com/Automall-Training/legal-engine.git ~/legal-engine
cd ~/legal-engine && SKILLS_DIR=~/.agents/skills bash ./install.sh
```

Нужны программа `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`, потом заново открыть Терминал) и Python 3.10 или новее: на Mac системный Python старше, поэтому `uv python install 3.12 --default`, снова открыть Терминал и проверить `python3 --version`. Команда `git` на чистом Mac попросит «инструменты разработчика» — установите и повторите. Дождитесь `READY`, перезапустите Codex и напишите `$legal-workflow-setup настрой юриста`. Строку скрипта «open Claude Code…» в этом случае пропустите. Папку `~/legal-engine` не удаляйте: скиллы подключены к ней ссылками. Пошагово, для тех, кто не открывал Терминал, — плейбук команды Automall: https://automall-playbook.vercel.app, страница «Скиллы», блок «Юристам».

### Безопасность

- Ключи API не нужны: поиск законов идёт через встроенный веб Claude Code или бесплатный браузер.
- Документы и сайты для движка — данные, а не команды.
- Движок ничего не подписывает, не отправляет и не публикует сам.

---

## Română

Un set de skill-uri pentru [Claude Code](https://claude.com/claude-code): jurist pentru dreptul
**Republicii Moldova, României și UE**, configurat pentru afacerea dumneavoastră printr-un interviu scurt.
Motorul nu conține datele nimănui; tot ce este al dumneavoastră (firme, nișe, contracte, legi descărcate)
stă în **profilul** de pe calculatorul dumneavoastră și nu ajunge niciodată în acest depozit. Ce scrieți în
conversație și documentele citite de agent sunt prelucrate de serviciul AI ales (de exemplu, Claude), conform
condițiilor furnizorului său.

**Module:** contracte, întrebări juridice cu surse oficiale, biblioteca și monitorizarea legilor (de bază);
date personale, vânzări online către consumatori, mărci, resurse umane (se activează în asistent).

**Instalare:** ca mai sus (`git clone …` și `./install.sh`), apoi în Claude Code: **«configurează juristul»**.
Actualizare: `git pull && ./install.sh`.

---

## License

MIT, for the code and the texts (skills, references, catalogs, clause modules): see [LICENSE](LICENSE).
Not covered: official legal texts (laws, EU acts, standard contractual clauses) quoted or downloaded by the
engine keep their own status and the rules of their publisher; third-party sample documents named in the clause
library are only linked, under their own licences. This is not legal advice: [DISCLAIMER.md](DISCLAIMER.md).
