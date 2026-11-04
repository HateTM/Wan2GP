# WanGP Studio — интеграционная архитектура (аудит и спецификация)

Дата: 2026-11-04. Статус: **аудит завершён, код не изменялся; слияний не выполнялось.**
Объект: web-приложение WanGP Studio (`plugins/wan2gp_studio`, ветка `fork/feat/wan2gp-studio-v0.1`, v0.1, минимальная версия ядра 18.84) и шесть существующих плагинов экосистемы.
Метод: чтение кода (только чтение), `git show` для ветки Studio, GitHub API для лицензий, анализ конфигов рабочего дерева (`main`, `64dee5cf`).
Источники-приложения: `specs/studio-audit/wanflow-ui.md`, `specs/studio-audit/plugin-apis.md`, `specs/studio-audit/media-world.md` (локальные, git-ignored).

---

## 0. Резюме

| Компонент | Происхождение | Лицензия (проверено) | Уровень интеграции | Ключевое ограничение |
|---|---|---|---|---|
| `wan2gp_studio` (сам Studio) | ветка `fork/feat/wan2gp-studio-v0.1` | проект (HateTM) | — | v0.1: 11 маршрутов, SSE-опрос, история в памяти |
| `wan2gp-wanflow-ui` | локальная копия, собственный `.git` без remote | **Apache-2.0** (+ хостовая Community License в комплекте) | **L2** (фасад), L3 допустим | движок исполнения живёт только in-process; публичного upstream нет |
| `wan2gp-status-pro` | реестр, `github.com/totideyouover2026-max/...` | **Public domain** | **L2** (данные, не код) | вызываемого API нет, только инъекция в UI |
| `models_manager` | **bundled** (DeepBeepMeep), не в реестре | проекта | **L2** | — |
| `ImageSuite-Wan2GP` | реестр, `saintorphan/...` | **WanGP Community License 2.0** | **L1** | вендоринг запрещён лицензией |
| `wan2gp-lora-manager` | реестр, `Tophness/...` | **НЕТ (license: null)** | **L1** | копирование/импорт кода юридически запрещены |
| `wan2gp-queue-editor` | реестр, `Tophness/...` | **НЕТ (license: null)** | **L1** | то же |

Определения уровней:

- **L1 — навигация**: Studio только ссылается на вкладку/страницу плагина (deep-link), код и API не используются. Допустимо для любого плагина без юридических вопросов.
- **L2 — API**: Studio вызывает публичные функции/методы плагина в том же процессе (`app.plugin_manager.get_all_plugins()`, контрактные методы), не копируя код. Требует стабильного контракта и деградации при отсутствии плагина.
- **L3 — вендоринг**: код плагина копируется/форкается в Studio. Допустим только при лицензии, разрешающей распространение (Apache-2.0/PD с атрибуцией; Community License — нет; без лицензии — запрещено).

Три вывода, меняющие прежние редакции плана:

1. **`media_gallery.py` — не индексатор и не основа Gallery.** Это input-виджет слотов рантайма wanflow-ui (`RuntimeMediaGallery`). Media Center строится заново; у `media_gallery.py` другая полезная роль — паттерн выбора входных медиа (см. §4).
2. **У wanflow-ui нет публичного upstream** — локальная копия с собственным `.git` (5 коммитов, baseline «before local changes», remote не настроен). Значит «дождаться апстрим-PR» невозможно: интеграция означает, что мы де-факто мейнтейним форк.
3. **Опциональных зависимостей в ядре нет** — механизм реализуется на стороне Studio: presence-проба + реестр загруженных плагинов + контрактные методы (прецедент — `query_checkpoint_inventory` в models_manager).

---

## 1. Матрица: лицензии, происхождение, допустимый уровень интеграции

### 1.1 `wan2gp-wanflow-ui` (node editor + workflow engine)

- **Лицензия**: `LICENSE` — полный Apache License 2.0 (11.3 KB). `LICENSE.txt` (21.4 KB) — WanGP Community License 2.0, лицензия **хоста**, а не плагина (приложена как часть дистрибутива). `THIRD_PARTY_NOTICES.md` описывает слоение. SPDX-заголовков в исходниках нет, файла `NOTICE` нет.
- **Происхождение**: локальная копия, не через plugin manager. Собственный `.git`: ветка `master`, remote отсутствует, 5 коммитов от 2026-10-07, HEAD `9497ad2`, первый коммит `1e173b2` «Baseline: WanFlow UI 0.1.0 before local changes». В `plugins.json`/`plugins_local.json` не значится; в главном репо не трекается (`git ls-files` пуст). Публичный upstream веб-поиском не найден (средняя уверенность).
- **Метаданные**: v0.1.0, `wan2gp_version` пуст — пина совместимости нет.
- **Уровень**: **L2** (фасад поверх `run_graph`, §3). **L3 разрешён лицензией** (Apache-2.0: сохранить LICENSE + указать авторство; NOTICE отсутствует, но `THIRD_PARTY_NOTICES.md` надо перенести) — использовать как страховку, не как первый шаг.
- **Ключевой риск**: отсутствие upstream = отсутствие внешних исправлений; любые патчи остаются у нас.

### 1.2 `wan2gp-status-pro` (телеметрия)

- **Лицензия**: `LICENSE` — public domain (Unlicense-подобный текст: «free and unencumbered software released into the public domain»).
- **Происхождение**: реестр (`plugins.json`, version 1.0.2, url `github.com/totideyouover2026-max/wan2gp-status-pro`), локально установлена **v1.2.1 — свежее реестровой**. Прямое доказательство, что сторонние плагины обновляются независимо от реестра.
- **Поверхность**: ни вкладки, ни web-приложения, ни Deepy-инструментов. Работает инъекцией в UI ядра (`insert_after("gen_status", …)`) и обёртками глобальных функций (~26 `request_global`, включая `build_callback`, `generate_media`, `release_model`). Вызываемого API нет.
- **Уровень**: **L2 по данным, не по коду**: Studio получает те же метрики из тех же источников (callbacks `WanGPSession`, обёртка `build_callback`), не копируя код и не дублируя UI. Если появится потребность в его истории — договариваться с автором об экспорте, а не вендорить.
- **Риск**: обновления плагина могут менять набор обёрток; Studio не должна от них зависеть.

### 1.3 `models_manager` (инспекция моделей и диска)

- **Происхождение**: **bundled-плагин самого WanGP** (author DeepBeepMeep, `uninstallable: false`, в `plugins.json` отсутствует). Это не сторонний код.
- **Лицензия**: проекта (WanGP Community License 2.0).
- **Поверхность**: вкладка + крупный JS; 21 `request_global`, включая `app`; **сам является потребителем контрактного метода `query_checkpoint_inventory`** — перебирает все загруженные плагины (`plugin_manager.get_all_plugins()`), собирая их чекпойнты.
- **Уровень**: **L2** — Studio вызывает его методы через реестр или использует тот же контракт; удаление файлов остаётся за models_manager (не дублировать).

### 1.4 `ImageSuite-Wan2GP` (редактор изображений)

- **Лицензия**: `LICENSE.txt` — **WanGP Community License 2.0**. PLAIN-ENGLISH SUMMARY: бесплатное использование и модификация для себя, продажа выходов с кредитом WanGP; **запрещены** продажа/white-label/встраивание в платный продукт/платный API/SaaS/hosted/OEM без письменной лицензии.
- **Происхождение**: реестр (`saintorphan/ImageSuite-Wan2GP`, v0.3.0 = реестровой).
- **Поверхность**: вкладка + `insert_after("gallery_tabs", …)` (кнопка «Send current frame» в чужой галерее); генерация через нативный пайплайн ядра (`download_models`, `get_current_model_settings`, `release_model`); образец graceful-партнёрства: `_sendto_installed()` — presence-проба каталога + try-import (plugin.py:97-112).
- **Уровень**: **L1** (deep-link + паттерн SendTo для передачи кадров). Вендоринг кода исключён лицензией; встраивание через iframe/ссылку — допустимо, но требует юридической проверки границы «hosted» при коммерциализации.

### 1.5 `wan2gp-lora-manager` и `wan2gp-queue-editor` (Tophness)

- **Лицензия**: локально файла нет; в апстрим-репозиториях — **тоже нет** (см. §2). По умолчанию: «все права защищены», копирование и производные работы запрещены.
- **Происхождение**: реестр (`Tophness/wan2gp-lora-manager` v2.5.5, `Tophness/wan2gp-queue-editor` v1.1.0; версии совпадают с реестровыми).
- **Поверхность**: lora-manager — две вкладки, `add_custom_js`, работа с Civitai, методы инстанса (`get_local_preview_path`, `read_lset_data`); queue-editor — вкладка офлайн-редактора `queue.zip`, 20 `request_global` приватных функций очереди.
- **Уровень**: **L1 только**. До получения письменной лицензии от автора: никакого импорта, копирования, вендоринга. Нативные функции Studio (секция LoRA через `list_loras`, очередь через `WanGPSession`) реализуются независимо и не требуют этих плагинов.

---

## 2. Проверка LICENSE в репозиториях Tophness (факт-лист)

Метод: GitHub REST API, 2026-11-04.

| Репозиторий | `license` | Корневые файлы | `archived` | Последний push |
|---|---|---|---|---|
| `Tophness/wan2gp-lora-manager` | **null** | `__init__.py`, `plugin.py`, `plugin_info.json` | false | 2026-01-26 |
| `Tophness/wan2gp-queue-editor` | **null** | `__init__.py`, `plugin.py`, `plugin_info.json` | false | 2026-02-13 |

Выводы:

1. Файла LICENSE нет ни локально, ни в апстриме; GitHub не распознаёт лицензию. Юридический дефолт — **all rights reserved**.
2. Интеграция возможна только как L1 (ссылка) либо после явного разрешения автора. Запросить лицензию (MIT/Apache-2.0) — единственный путь к L2/L3; до этого код не копировать, не импортировать, не распространять в составе Studio.
3. Оба репозитория содержат ровно три файла — это однофайловые плагины; их функциональность мала и воспроизводима нативно (LoRA-секция Studio уже работает через `list_loras`; queue-editor — офлайн-инструмент, не пересекающийся с живой очередью).

---

## 3. wanflow-ui: варианты A/B/C интеграции

### 3.1 Что показал аудит (кратко)

- **Канвас переносим**: `editor.js` (555 строк) — vanilla JS/DOM+SVG без внешних библиотек и без fetch; рендерится в sandboxed `srcdoc`-iframe; протокол — `postMessage({type:'WAN2GP_WORKFLOWS_V2', action, graph})` + три начальных JS-глобала (`W2GP_INITIAL_GRAPH`, `W2GP_NODE_CATALOG`, `W2GP_STATUS`) в base64; мост в Gradio — `_bridge()` (скрытые кнопки + polling каждые 500 мс).
- **Исполнение — только in-process**: `run_graph` уходит в нативную очередь WanGP через `api_session.submit_task` (`GradioWanGPSession`), плюс приватные связки: `_ui_local` (thread-local сессия), `_process_inline_queue` (пробуждение инлайн-очереди), internals промпт-энхансера, `sys.modules["wgp"].server_config` (preflight). Вне живого процесса WanGP движок не работает.
- **Отмена существует, но не выставлена**: `cancel_check` проверяется на каждом узле, ffmpeg-операции прерываются, но `run_payload` вызывает `run_graph` без `cancel_check` и в UI кнопки отмены нет.
- **GPU-сериализация — только через нативную очередь**; `any_GPU_process_running` запрошен, но нигде не вызывается.
- **Кэш/резьюм полноценный**: TTL 6 ч, 300 записей, fingerprints файлов, env-выключатель `WANFLOW_NO_CACHE=1`.
- **Масштаб**: 4 264 строки Python + 1 871 строк тестов (11 файлов) + 616 строк ассетов; новых pip-зависимостей нет; ffmpeg через `resolve_media_binary`.
- **Внешней поверхности нет**: ни Deepy-инструментов, ни HTTP, ни `register_web_app`; 17 `request_global` + `state`.

### 3.2 Варианты

**A. Iframe/редирект на существующую Gradio-вкладку.**

- Как: в `/studio/` пункт «Workflow» открывает хост-вкладку wanflow-ui (или `AppFrameGuard`-iframe).
- Плюсы: ноль кода, ноль риска, полная функциональность уже сегодня. Минусы: две разные навигационные модели; Gradio-таб живёт в общем UI и не знает о Studio-сессиях; состояние workflow не переживает переходы; визуально не «раздел Studio».
- Вердикт: **временная мера** до готовности B; не целевое состояние.

**B. HTTP-фасад в процессе WanGP + перенос канваса.**

- Как: новый модуль Studio (`studio/workflow_facade.py` + маршруты `/studio/api/workflow/*`) импортирует модули wanflow-ui в том же процессе и вызывает `run_graph`; канвас `editor.js` переносится в `/studio/` как статический ассет; транспорт postMessage заменяется на fetch (или остаётся postMessage с родителем-страницей).
- Что даёт фасад: `GET catalog` (`build_catalog` + blocks), `GET/PUT workflow` (`GraphStore`), `POST run` (thread + события), `POST cancel` (передаёт `cancel_check` — закрывает главный пробел), `POST upload` (замена `RuntimeMediaGallery`), `GET events` (SSE вместо polling превью).
- Плюсы: единый UX; отмена появляется сразу; движок не дублируется (правило «один runtime»); канвас не переписывается. Минусы: Studio обязана повторять приватные связки (`_ui_local`-копирование в поток, `_process_inline_queue`, `server_config`) — это хрупкие точки, требующие адаптера и версионного гейта; при отсутствии wanflow-ui секция деградирует.
- Вердикт: **рекомендуется**, поэтапно: B0 — read-only каталог → B1 — run/cancel через `run_graph` → B2 — канвас в `/studio/` (замена моста).

**C. Вендоринг движка в Studio (полный форк).**

- Как: копировать `runtime_engine.py`, `graph_runner.py`, `graph_model.py` и др. в Studio, отказавшись от плагина как зависимости.
- Плюсы: полный контроль, лицензия Apache-2.0 позволяет, исчезает зависимость от «чужого» каталога. Минусы: 4.3k строк + 1.9k тестов переходят на наше обслуживание; два экземпляра движка в экосистеме (плагин и Studio) начнут расходиться; правило 5 Roadmap v2 («никакого дублирования workflow-движков») нарушается с первого дня; upstream отсутствует, значит синхронизации не будет вообще.
- Вердикт: **отклонить как первый шаг**; держать как страховку (лицензия позволяет), если вариант B упрётся в приватные API ядра.

### 3.3 Рекомендация

**Вариант B.** Обоснование: единственный вариант, который одновременно (а) сохраняет один workflow-движок, (б) даёт Studio полноценный раздел, (в) закрывает дыру с отменой, (г) не требует правок ядра. Обязательные условия:

1. Адаптер изоляции: все приватные обращения — в одном модуле `workflow_compat.py` с проверкой версии ядра (`wan2gp_version` ≥ 18.84) и try/except с деградацией.
2. Presence-detection: нет каталога `plugins/wan2gp-wanflow-ui` → секция «не установлен», остальное работает.
3. Патчи wanflow-ui (если понадобятся) ведутся в нашей копии и фиксируются в `THIRD_PARTY_NOTICES.md` + `LICENSE` (Apache-2.0).

---

## 4. `media_gallery.py` и поддержка `.wgpworld`

### 4.1 Что такое `media_gallery.py` на самом деле

`RuntimeMediaGallery` (145 строк) — **виджет входных материалов** для workflow: упорядоченный список локальных путей (`{"items":[paths],"selected":n}`), кнопки add/remove/left/right/clear, подаётся в `run_payload` и потребляется input-слотами (`graph_runner.py:859-865`). Он не сканирует выходы, не индексирует медиа, не знает о `.wgpworld` (расширения ограничены). `workflow_outputs/` — рантайм-каталог промежуточных медиа-узлов, не галерея; сгенерированные WanGP файлы остаются в общих корнях вывода.

**Следствие для Roadmap v2**: «использовать `media_gallery.py` как основу Gallery» — некорректная посылка. Правильные варианты использования:

- **(и)** применить как **паттерн выбора входных медиа** в Studio (upload/drag&drop → упорядоченные слоты → параметры генерации) — да;
- **(ии)** индексатор Media Center писать заново — да;
- **(иии)** вендорить код виджета — не нужно, он тривиален и завязан на Gradio.

### 4.2 Реальная карта медиа-хранилища (факты)

- **4 корня вывода**: `save_path` (видео/`.wgpworld`), `image_save_path`, `audio_save_path`, `mesh_save_path` (дефолт `outputs`, переопределение `--output-dir`). На этой машине все четыре = `C:\Wan2GP-Models\outputs`, **313 файлов плоско**, 0 JSON-сайдкаров.
- **Workspace-redirect**: в режиме `dedicated` пути подменяются на папку workspace (`workspace_storage.output_config`); `workspaces/*.json` — единственный персистентный индекс галерей на диске.
- **Метаданные — встроенные, 6 механизмов**: MP4 `©cmt`/MKV comment (mutagen/ffmpeg), PNG comment/EXIF UserComment, WAV RIFF-чанк `json`/ID3 TXXX, мир — `settings.json` внутри zip. Режим сайдкаров `<stem>.json` **существует, но выключен** (`metadata_type: "metadata"` в `wgp_config.json`).
- **Имена**: `{timestamp}_seed{seed}_{prompt}.{ext}`; связки: `<stem>.mp4` + `<stem>.wgpworld` (world — side-file рядом с видео), `<stem>_explored.wgpworld`/`<stem>_exploration.mp4` (результаты исследования).
- **Миниатюры**: готовый on-demand движок Deepy (`shared/deepy/thumbnails.py`: 2 потока, lru 256, JPEG ≤512×384 q80, ключ sha1(path|mtime|size); видео — кадр ffmpeg; `.wgpworld` — `thumbnail.jpg` из zip; картинки — PIL) + HTTP-эндпоинт `/deepy_api/workspace_viewer/thumbnail`. Дисковых миниатюр никто не пишет — второй движок строить не нужно.
- **`.wgpworld`**: **несжатый zip** (ZIP_STORED): `manifest.json` (format=`wgpworld`, version=1, model_type, w/h, fps, seed, сегменты с instruction/keys/event), `tensors.safetensors` (латенты/позы/память), `thumbnail.jpg`, `poster.jpg`; после генерации дописывается `settings.json`. Explorer — JSON-протокол start/move/leave/render/save/stats; клипы — `<save_path>/.world_exploration/<token>_NNNN.mp4` (эфемерные); команды `[Forward 3s]`, `[Look_Left 1.5]`, `[Wait]`, `[Event] …` парсятся `world_instructions.py`.

### 4.3 Спецификация Media Center (P1)

1. **Индексатор** (новый модуль Studio): обход 4 корней + workspace-dedicated папок + `workflow_outputs/` (опционально); чтение встроенных метаданных **существующими парсерами ядра** (`media_recording`, `video_metadata`, `audio_video`, `audio_metadata`, world `settings.json`); для `.wgpworld` — manifest+settings из zip. Никакого нового формата метаданных не вводить.
2. **Кэш индекса**: SQLite (опция Roadmap v2 допускает) — только Studio, вне репо; инвалидация по (path, size, mtime).
3. **Миниатюры**: проксировать Deepy-движок (переиспользовать `/deepy_api/.../thumbnail` или импортировать `thumbnails.py`), лимиты 512×384/JPEG — задокументировать как достаточные для сетки.
4. **Worlds**: отдельный фильтр; превью — `thumbnail.jpg`/`poster.jpg` из zip; открытие — существующий Worlds explorer (deep-link на нативную вкладку), продолжение мира `custom_guide` — через генерацию Studio.
5. **Опционально**: включение json-сайдкаров (`metadata_type: "json"`) как пользовательская настройка — это конфиг, не код; даёт Media Center дискретные метаданные без правок ядра.
6. **Производительность**: виртуализация списка на клиенте; сервер отдаёт страницы по 50–200 записей; видео-байты не читаются на сервере, кроме миниатюр.

---

## 5. Архитектура опциональных зависимостей и graceful degradation

Ядро не предоставляет механизма зависимостей (проверено: в `plugin_info.json` нет `requires`/`dependencies`; `restricted_globals` пуст; гейт только по `wan2gp_version`). Механизм реализуется целиком в Studio.

### 5.1 Обнаружение (три источника, порядок)

1. **Реестр загруженных плагинов**: `request_global("app")` → `app.plugin_manager.get_all_plugins()` — видит только **включённые** плагины (прецедент: `guides` вызывает `about.create_about_ui()`, models_manager перебирает чекпойнты).
2. **Presence-проба каталога**: `os.path.isdir("plugins/<name>")` + try-import (паттерн ImageSuite↔SendTo) — видит установленные, но выключенные.
3. **Контрактные методы**: `query_checkpoint_inventory()` — единственный «плагин→плагин» протокол в ядре; расширяем по аналогии (`studio_capabilities()` как новый опциональный метод — только для плагинов, которые мы контролируем: bundled-плагины и Studio-совместимые).

### 5.2 Единый реестр возможностей Studio

`GET /studio/api/environment` — один ответ:

```json
{
  "core": {"version": "18.84", "auth": true},
  "plugins": [
    {"id": "wan2gp-wanflow-ui", "state": "enabled", "version": "0.1.0",
     "capabilities": ["workflow.catalog", "workflow.run"],
     "integration": "L2"},
    {"id": "wan2gp-lora-manager", "state": "enabled", "version": "2.5.5",
     "capabilities": [], "integration": "L1", "reason": "no-license"}
  ]
}
```

Фронтенд строит навигацию **из этого ответа**, а не из хардкода; каждый раздел имеет состояние: `available | not_installed | disabled | incompatible | unlicensed`.

### 5.3 Правила деградации (обязательные)

1. Ни один импорт чужого плагина не выполняется на уровне модуля — только лениво, внутри функции, в try/except.
2. Любой вызов чужого плагина ограничен тайм-аутом; исключение = раздел помечается `unavailable`, Studio продолжает работать.
3. Отсутствие плагина никогда не ломает генерацию, галерею и очередь — только скрывает соответствующий раздел/кнопку.
4. Для L1-плагинов UI показывает deep-link на их вкладку (с подписью «откроется в основном интерфейсе»), а не пытается встроить.
5. Версии фиксируются в `/api/environment`; несовпадение мажора — `incompatible` с объяснением.
6. Лицензионный статус — часть реестра: `integration: "L1"` с причиной `no-license` отображается в «Системе».

---

## 6. API-контракты и точки интеграции

### 6.1 Studio ↔ ядро WanGP

| Контракт | Где | Что использует Studio |
|---|---|---|
| `deepy.web_session()` → `WanGPSession` | `shared/deepy/plugin_jobs.py:567-580` | `submit_task`, `list_model_metadata`, `get_model_def/settings/schema`, `merge_settings_with_defaults`, `list_loras`, `SessionJob.result/cancel` |
| callbacks | `shared/api.py:1163-1176` | duck-typing `on_status/on_progress/on_preview/on_error` + `on_event` |
| `register_web_app(path, factory)` | `shared/utils/plugins.py:530-539` | `/studio` (валидация пути, резерв путей) |
| `WebAuthMiddleware` | `shared/authentication/web.py:137-167` | cookie `wangp_session`, 24 ч, same-origin на POST; без `--auth` гейт отключён |
| `request_global` | `plugins.py:494` | доступ к любым глобалам ядра (`restricted_globals` пуст) |
| `add_custom_js` / `request_component` | `plugins.py:526/490` | JS-инъекции, общий `state` |

### 6.2 Studio ↔ web-клиент (маршруты)

Существующие (v0.1): `GET /`, `/api/health`, `/api/models`, `/api/models/{type}`, `/api/models/{type}/settings`, `/api/jobs` (GET/POST), `/api/jobs/{id}`, `/api/jobs/{id}/events` (SSE), `/api/jobs/{id}/cancel`.

Планируемые (v0.2+): `GET /api/environment` (§5.2), `GET /api/media` (страницы, фильтры), `GET /api/media/{id}/thumbnail`, `GET|PUT /api/workflows`, `POST /api/workflows/{id}/run`, `POST /api/workflows/{id}/cancel`, `POST /api/workflows/{id}/inputs`, `GET /api/telemetry` (SSE), `GET /api/worlds/{id}`.

### 6.3 Studio ↔ wanflow-ui (вариант B)

| Операция | Реализация фасада | Хрупкая зависимость |
|---|---|---|
| Каталог | `node_registry.build_catalog` + `BlockStore.catalog` | `extra_settings.iter_defs`, `postprocessing.catalog` |
| Чтение/запись workflow | `GraphStore` (`workflows/*.json`, атомарная запись) | — |
| Запуск | `run_graph(...)` в потоке, `submit_task` внутрь | `_ui_local`-копирование, `_process_inline_queue` |
| Отмена | `cancel_check` → `job.cancel()` | — (механизм есть) |
| События | колбэки узлов → очередь → SSE | формат событий плагина |
| Входные материалы | upload → пути (замена `RuntimeMediaGallery`) | — |
| Preflight | `preflight.check()` | `sys.modules["wgp"].server_config` |

Правило: все строки таблицы живут в `workflow_compat.py`; при расхождении версий — деградация до варианта A (deep-link).

### 6.4 Studio ↔ остальные плагины

- **models_manager** (L2): методы через реестр + `query_checkpoint_inventory`; удаление файлов — только его UI (deep-link).
- **status-pro** (L2-данные): телеметрия из тех же источников, что оборачивает он (`build_callback`, callbacks сессии); UI не дублировать, историю запрашивать у автора при необходимости.
- **ImageSuite** (L1): deep-link на вкладку; передача кадров — SendTo-паттерн (поверхность `/api/media/{id}` + клик пользователя в их UI).
- **lora-manager / queue-editor** (L1): deep-link; нативные функции Studio не зависят от них.

### 6.5 Зафиксированные «хрупкие точки» (требуют адаптера)

1. `api_session._ui_local` (thread-local Gradio-контекст) — копировать в воркер как `plugin_ui.py:422-430`.
2. `service._process_inline_queue` — пробуждение инлайн-очереди (`graph_runner.py:107`).
3. `sys.modules["wgp"].server_config` — preflight (`preflight.py:75-82`).
4. Internals промпт-энхансера (`ai_runtime.py:40-96`).
5. `build_callback`-обёртки (status-pro) и `plugin.state`-биндинг.

Для каждой — try/except, лог, деградация; тест на смоук при обновлении ядра.

---

## 7. План миграции без изменения ядра Wan2GP

Инвариант: **ни один шаг не меняет `wgp.py`, `shared/`, `models/`** — только `plugins/wan2gp_studio/` (и, при необходимости, локальная копия `plugins/wan2gp-wanflow-ui/`). Проверка на каждом шаге: `git diff --stat -- wgp.py shared models` пуст.

| Шаг | Содержание | Зависимости | Правки ядра |
|---|---|---|---|
| **M0 (P0)** | Слить `fork/feat/wan2gp-studio-v0.1` в `main` (merge-tree чистый), включить плагин, пройти чек-лист Этапа 0 на реальных моделях; исправить `AGENTS.md` (ветка/статус) | — | 0 |
| **M1 (P1)** | Media Center: индексатор 4 корней + workspace + встроенные метаданные; `/api/media`; миниатюры через Deepy-движок; виртуализация | §4 | 0 |
| **M2 (P2)** | Workflow: `workflow_compat.py` + фасад `/api/workflow/*`; перенос `editor.js`; отмена; `/api/environment` | вариант B, §3, §5 | 0 |
| **M3 (P3)** | Resource Center: телеметрия из callbacks Studio + psutil; NVML-обёртка (util/temp/power/fan) — отдельный маленький модуль; согласование с status-pro | §6.4 | 0 |
| **M4 (P4)** | Model Center: каталог Studio + models_manager L2; LoRA-секция нативная; очередь — `WanGPSession` + deep-link queue-editor | §1.3, §1.5 | 0 |
| **M5 (P5)** | Editing: ImageSuite deep-link + SendTo-передача кадров; никакого копирования кода | §1.4 | 0 |
| **M6 (P6–P7)** | Формат workflow: `wan2gp-wanflow-ui` v1 — основной; ComfyUI — только адаптер импорта/экспорта после подтверждения совместимости; production-тесты/документация | — | 0 |

Примечания:

- M2 включает «страховочный» сценарий: если фасад упирается в приватные API — откат на вариант A (deep-link), без потери остальных разделов.
- M0 может быть выполнен независимо и первым: слияние проверено (`git merge-tree` — конфликтов нет), ветка трогает только `plugins/wan2gp_studio/` (988 строк), `register_web_app` уже есть в `main`.
- Порядок M1→M2 соответствует приоритетам Roadmap v2; M3 можно вести параллельно M2 (не пересекаются).

---

## 8. Риски обновления сторонних плагинов и критерии приёмки

### 8.1 Риски и меры

| # | Риск | Вероятность/эффект | Мера |
|---|---|---|---|
| R1 | Лицензии Tophness отсутствуют | высокая / юридический блок L2+ | L1; запрос лицензии автору; нативная реализация функций |
| R2 | У wanflow-ui нет upstream; мы де-факто мейнтейнеры | высокая / средний | зафиксировать форк, `THIRD_PARTY_NOTICES.md`, патчи только у нас; L3 как страховка |
| R3 | Независимые обновления (status-pro 1.2.1 > реестр 1.0.2) ломают инъекции | средняя / средний | capability-реестр, версии, деградация; не полагаться на приватные поля чужих плагинов |
| R4 | Приватные API ядра (`_ui_local`, `_process_inline_queue`, `server_config`) меняются | средняя / высокий | адаптер `workflow_compat.py`, гейт `wan2gp_version`, смоук после каждого мерджа upstream |
| R5 | WanGP Community License 2.0 ограничивает платный SaaS/hosted | низкая сейчас / высокий при коммерциализации | держать Studio в некоммерческом форке; юрпроверка перед любым платным сценарием |
| R6 | Дублирование телеметрии/мониторинга | средняя / нарушение правил Roadmap v2 | единый источник данных, §6.4; UI не дублировать |
| R7 | 6 механизмов метаданных, сайдкары выключены | высокая / средний | читать существующими парсерами; тесты на фикс-файлах; json-сайдкары как opt-in |
| R8 | `editor.js` — единственная копия канваса без upstream | средняя / средний | вендоринг-путь (Apache-2.0), тесты `test_plugin_import` как база |

### 8.2 Критерии приёмки по шагам

**M0**: чек-лист Этапа 0 (плагин грузится через Plugin Manager, `/studio/` открывается, авторизация работает при `--auth`, каталог моделей отдаётся, пресеты/LoRA доступны, генерация запускается, SSE идёт, отмена срабатывает, ошибки показываются) — всё зелёное на реальных моделях; `python -m pytest plugins/*/tests` не хуже базовой линии; `wgp.py --process settings.json --dry-run` проходит.

**M1**: индексатор находит все 4 корня и workspace-папки; для MP4/PNG/WAV извлекаются prompt/seed/параметры; `.wgpworld` распознаётся и открывается; первый экран ≤2 с на 10 тыс. записей; сервер не читает видео-байты (кроме миниатюр); память процесса не растёт при прокрутке.

**M2**: создание/сохранение/запуск workflow из `/studio/`; отмена из UI останавливает узел ≤1 с; при отсутствии wanflow-ui раздел показывает `not_installed`, генерация и галерея работают; `git diff` по ядру пуст; смоук-тест фасада против `build_catalog`.

**M3**: показатели обновляются ≤1 с при генерации; нет второго аллокатора/мониторинга (только чтение); NVML-метрики помечены как опциональные и не ломают запуск без них.

**M4**: каталог/профили/LoRA/очередь доступны без lora-manager и queue-editor; удаление файлов только через models_manager (deep-link).

**Общие**: каждый новый маршрут под `WebAuthMiddleware`; SSE не держит большие буферы; при отключении любого стороннего плагина Studio стартует и показывает деградацию; ни один шаг не требует правок `wgp.py`/`shared/`.

---

## Приложение A. Открытые вопросы

1. Сверить контракты с `docs/PLUGINS.md` и `docs/API.md` (разведка шла по коду; нормативные документы не читались).
2. Юридическая проверка WanGP Community License 2.0 для сценария `/studio/` (граница «hosted/SaaS») — перед любой коммерциализацией.
3. Публичный upstream wanflow-ui не найден — подтвердить у автора (Javier), нет ли закрытого/приватного репозитория.
4. Достаточность миниатюр 512×384 q80 для сетки Media Center (иначе — параметр движка, не новый движок).
5. Судьба `models/waypoint` (в рабочем дереве только `__pycache__`, исходников нет) — вне скоупа аудита, но влияет на раздел Worlds.

## Приложение B. Что НЕ делалось

- Код не изменялся, ветки не сливались, генерация не запускалась.
- Построчный юридический разбор Community License не выполнялся.
- Живая проверка `_wake_webui_queue`/preflight не проводилась (только чтение кода).
- `docs/PLUGINS.md`/`docs/API.md` не сверялись (см. A.1).
