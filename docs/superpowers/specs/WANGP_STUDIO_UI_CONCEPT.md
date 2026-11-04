# WanGP Studio — UI Concept

> Целевой UX и визуальная спецификация. Это концепт будущих этапов, а не перечень функций, уже реализованных в v0.1.
>
> Roadmap: ../plans/WANGP_STUDIO_ROADMAP_V3.md
> Архитектурный аудит: STUDIO_INTEGRATION_ARCHITECTURE.md
> SVG preview: ../assets/wan2gp-studio-ui-concept.svg

## 1. Направление

WanGP Studio выглядит как профессиональное desktop creative application, а не как тяжёлая админ-панель и не как копия ComfyUI.

- Dark-first, графитовые нейтральные поверхности.
- Workflow-first: canvas — центральная рабочая область.
- Model-aware: параметры соответствуют реальной schema выбранной модели.
- Media-centric: исходники и результаты собраны в одной библиотеке.
- Runtime-aware: очередь и ресурсы видны, но не доминируют.
- Low-overhead: тонкий UI над существующим runtime.

Не использовать динамические градиенты, постоянный backdrop blur, декоративный WebGL, непрерывные анимации и тяжёлые графики на каждом экране. Не добавлять frontend framework без измеримого основания.

## 2. Информационная архитектура

| Раздел | Назначение | Тип |
|---|---|---|
| Dashboard | Недавняя активность, active jobs, shortcuts | Native |
| Generate | Быстрый запуск через WanGPSession | Native |
| Workflow | Графы и исполнение wanflow-ui | Optional L2 |
| Media Center | Images, Videos, Audio, Worlds | Native |
| Image Editor | Переход в ImageSuite + SendTo | Optional L1 |
| Models | Каталог, schema, presets, LoRA | Native + bundled L2 |
| Queue | Studio jobs и доступная часть native queue | Native |
| Resource Center | VRAM/RAM/GPU/runtime telemetry | Read-only |
| Settings | Настройки Studio и диагностика зависимостей | Native |

Sidebar-группы: WORKSPACE (Dashboard, Generate, Workflow), LIBRARY (Media Center, Image Editor), MANAGE (Models, Queue), SYSTEM (Resource Center, Settings).

Навигация строится по capability registry. Optional section не ломается и не исчезает бесследно: показывает not_installed/disabled/incompatible/unlicensed и разрешённый переход к Plugin Manager или штатной вкладке.

## 3. Desktop layout

Основной экран Workflow:

    ┌──────────────────────┬─────────────────────────────────────────────────────────────┐
    │ WanGP Studio         │ Workspace / Workflow               Runtime: Connected      │
    ├──────────────────────┼─────────────────────────────────────────────────────────────┤
    │ WORKSPACE            │ Workflow: Untitled                  Save   Run   More       │
    │  Dashboard           ├──────────────┬──────────────────────────────┬───────────────┤
    │  Generate            │ NODE LIBRARY │                              │ INSPECTOR     │
    │  Workflow            │              │                              │               │
    │                      │ Inputs       │         WORKFLOW CANVAS      │ Node settings │
    │ LIBRARY              │ Models       │                              │ Model         │
    │  Media Center        │ Generation   │   Prompt → Wan I2V → Output  │ Parameters    │
    │  Image Editor        │ Processing   │                              │ LoRA          │
    │                      │ Outputs      │                              │               │
    │ MANAGE               ├──────────────┴──────────────────────────────┴───────────────┤
    │  Models              │ EXECUTION / QUEUE                                    ▴     │
    │  Queue               │ Running · Step 12/30 · ETA · Cancel                       │
    │                      ├─────────────────────────────────────────────────────────────┤
    │ SYSTEM               │ WanGP Studio                                      v0.x      │
    │  Resource Center     │                                                             │
    │  Settings            │                                                             │
    │ Runtime connected    │                                                             │
    └──────────────────────┴─────────────────────────────────────────────────────────────┘

Для ширины 1440–1600 px: sidebar 208–224 px, node library 220–250 px, inspector 280–320 px, execution drawer 150–190 px expanded, header 48–56 px. Canvas занимает всё оставшееся пространство. На меньших экранах Library/Inspector становятся drawers.

## 4. Workflow

### Node Library
Категории Inputs, Models, Generation, Processing, Control, Outputs. Каталог берётся из wanflow-ui runtime. Недоступные или несовместимые узлы нельзя показывать как доступные. Карточка: название, назначение, категория, статус, input/output types. Поиск локальный по загруженному каталогу.

### Canvas
- Нейтральная низкоконтрастная сетка.
- Чёткие прямоугольные узлы.
- Цвет портов кодирует тип данных.
- Тонкие линии связей, без движущихся частиц.
- Pan/zoom, optional minimap, видимый selection.
- Ошибка отображается на узле и в execution log.
- Сохраняется семантика исходного wanflow-ui; не переписывать graph engine ради визуала.

### Inspector
Контекстный: выбранный node, model-specific controls, generation prompt/negative prompt/seed, media source/metadata, workflow settings. Schema и defaults приходят из WanGP. Не создавать универсальную форму с несуществующими параметрами.

### Toolbar
Имя, save state, Undo/Redo (если поддерживается), zoom, Validate, Run, Cancel, More (duplicate/import/export). Недоступные действия disabled с объяснением.

## 5. Generate

Упрощённый запуск без сборки графа:
- model selector + availability;
- prompt / negative prompt;
- input media slots по возможностям модели;
- native presets/profiles;
- LoRA inventory;
- основные и advanced settings JSON;
- Run;
- result preview и переход в Gallery.

Поля строятся из model schema; неподдерживаемые параметры скрываются; расширенные/неизвестные поля JSON не теряются. Submit всегда через WanGPSession и native queue.

## 6. Media Center

Toolbar: search, filters, sort, view mode. Фильтры: All, Images, Videos, Audio, Worlds. Основная область — virtualized grid/list. Details panel — metadata, prompt, model, seed, dimensions, duration. Preview — image viewer или native video/audio element.

Media card содержит thumbnail, type, короткое имя, дату, dimensions/duration, model label. Оригиналы не загружать в frontend memory; thumbnail запрашивать при появлении карточки в viewport.

Worlds — самостоятельный media type, не просто MP4:
- poster/thumbnail из .wgpworld;
- model/date/dimensions/FPS/segment count;
- ссылка на exploration video;
- Open in World Explorer.

## 7. Image Editor

Не дублировать ImageSuite. Если установлен: Open ImageSuite, Send selected media. Передавать только выбранный пользователем файл/frame. Если отсутствует/disabled: показать dependency state и Plugin Manager link; Gallery и Generate остаются рабочими.

## 8. Models

Installed models, type filters, search, availability, details, presets/profiles, LoRA inventory, compatibility/capabilities. Bundled models_manager отвечает за принадлежащие ему destructive operations. Tophness plugins без лицензии — только внешние ссылки.

## 9. Queue и execution drawer

Queue page показывает Studio tasks и только те native queue statuses, которые реально доступны через API: model, task type, submitted time, progress, terminal state, error, cancel/open result. Не обещать полный native queue overview, если контракт этого не даёт.

Bottom drawer: Running, Queued, Completed/Failed, current step, ETA if available, Cancel, Expand to Queue. Не анимировать непрерывно, когда drawer закрыт.

## 10. Resource Center

Только реально доступные значения: GPU utilization, VRAM, temperature/power/fan (если NVML), process RAM, system RAM, MMGP allocation/offloading, current model/task, generation timing/ETA. Неизвестное значение показывать как unavailable, не как ноль.

Визуализация — компактные числа, простые статические bars, sparklines только при полезной истории. Не превращать экран в стену графиков.

## 11. Design tokens

| Token | Value | Назначение |
|---|---|---|
| bg | #0D1117 | основной фон |
| sidebar | #10161F | навигация |
| panel | #151C26 | панели |
| raised | #1A2430 | выбранные панели/узлы |
| border | #293545 | границы |
| text | #E6ECF4 | основной текст |
| muted | #8B98A9 | вторичный текст |
| accent | #86A7F2 | primary action/selection |
| success | #65C99E | success |
| warning | #D6AD70 | warning |
| danger | #D98288 | error/cancel |

Typography: system UI; Inter только если доступен локально. Основной 12–14 px, вторичный 11–12 px, labels 9–10 px, page title 20–24 px. Code/JSON — monospace. Spacing base 4 px; gaps 8/12/16/24; radius 5–8 px. Нейтральные borders, минимум теней.

Motion: короткие hover/focus/panel transitions; уважать prefers-reduced-motion; никаких постоянных animation loops.

## 12. Responsive

- ≥1440 px: sidebar + library + canvas + inspector.
- 1024–1439 px: compact sidebar, collapsible library/inspector.
- 680–1023 px: compact navigation, drawers, canvas priority.
- <680 px: основные сценарии — Generate, просмотр media, Queue; сложное graph editing не primary mobile use case.

## 13. Accessibility

Семантические controls, видимый keyboard focus, контраст, состояния не только цветом, keyboard navigation, labels для icon-only controls, корректный focus management, keyboard alternatives для canvas и reduced-motion.

## 14. Performance rules

Целевая конфигурация: RTX 5070 Ti Laptop 12 GB, 32 GB RAM, Windows 11.

1. Статические HTML/CSS/JS assets на сервере WanGP.
2. Нет второго frontend server.
3. Нет framework/state stack без отдельного обоснования.
4. Lazy-load разделов и virtualize длинные списки.
5. Thumbnails только для видимых карточек.
6. Bounded browser cache, job history и SSE buffers.
7. Не хранить full media bytes в JS state или долгоживущих backend objects.
8. Не создавать GPU workers.
9. Не делать тяжёлый polling при неактивном экране.
10. Не дублировать MMGP/status-pro telemetry.
11. Нет динамических градиентов и декоративной анимации.

До/после этапов фиксировать idle RAM, RAM при Gallery scroll, idle CPU, SSE connections, DOM nodes, long-session behavior и memory growth. Численные budgets утверждать после baseline замеров.

## 15. UI states и критерии приёмки

Каждый раздел поддерживает Loading, Ready, Empty, Error, Unavailable, Not installed, Disabled, Incompatible, Unlicensed, Runtime disconnected.

Концепт принят, если canvas — главный рабочий элемент; параметры и навигация доступны без перегруза; интеграции честно показывают свой статус; Gallery одинаково поддерживает images/videos/audio/Worlds; runtime виден, но не доминирует; экран читаем на 1440 px и адаптивен; тяжёлых декоративных эффектов нет; UI не дублирует backend/runtime.

**Итог:** цельный профессиональный инструмент с лёгким интерфейсом поверх существующего WanGP.
