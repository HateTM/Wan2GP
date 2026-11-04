# WanGP Studio — Roadmap v3

> Рабочий план реализации по результатам интеграционного аудита. Статус документа — план, не подтверждение готовности перечисленных функций.
>
> Базовая ветка: feat/wan2gp-studio-v0.1
> Базовая реализация: plugins/wan2gp_studio, v0.1; минимальное ядро WanGP 18.84
> Архитектура: ../specs/STUDIO_INTEGRATION_ARCHITECTURE.md
> UI-концепт: ../specs/WANGP_STUDIO_UI_CONCEPT.md
> SVG-макет: ../assets/wan2gp-studio-ui-concept.svg

## 1. Цель продукта

WanGP Studio — единая лёгкая рабочая среда для генерации, редактирования и организации изображений, видео, аудио и World-контента. Studio является UX-слоем над WanGP, а не отдельным генератором и не параллельным runtime.

Основные сценарии:
- запуск генерации через нативные model definitions, settings, presets и LoRA;
- создание и выполнение визуальных workflow;
- импорт, просмотр, поиск и повторное использование медиа;
- переход к ImageSuite для редактирования;
- просмотр задач, очереди и доступной телеметрии;
- работа с файлами .wgpworld и существующим World Explorer.

## 2. Архитектурные инварианты

1. Один WanGP Runtime, одна нативная очередь GPU-задач и один MMGP allocator/offloading.
2. Не вводить второй FastAPI/web server: использовать register_web_app, существующий сервер WanGP и SSE.
3. Не менять wgp.py, shared/ и models/: изменения ограничить Studio и допустимыми адаптерами плагинов.
4. Перед реализацией функции проверять нативные API и существующие плагины. Не дублировать уже реализованное.
5. Все сторонние плагины — optional dependencies. Их отсутствие, отключение, удаление или несовместимость не должны ломать Studio.
6. Импорт сторонних модулей выполнять лениво, внутри адаптеров, с обработкой исключений и version/capability checks.
7. Не создавать собственный allocator, очередь генерации, thumbnail engine или тяжёлую систему телеметрии.
8. UI поставляется как статические HTML/CSS/JS assets; отдельный frontend dev server не требуется в production.
9. Новые маршруты защищаются существующим WebAuthMiddleware; SSE, job history и кэши ограничены по памяти.
10. Лицензионные ограничения обязательны. Отсутствие LICENSE не означает разрешения на копирование кода.

## 3. Интеграционная матрица

| Компонент | Уровень | Правило |
|---|---|---|
| wan2gp-wanflow-ui | L2, L3 допустим | Предпочесть in-process facade над run_graph; Apache-2.0 допускает вендоринг с атрибуцией и сохранением THIRD_PARTY_NOTICES |
| wan2gp-status-pro | L2 по данным | Читать собственные источники метрик; не зависеть от UI-инъекций и не копировать код |
| models_manager | L2, bundled | Использовать существующий контракт; destructive file operations оставить его штатному UI |
| ImageSuite-Wan2GP | L1 | Deep-link и SendTo; не вендорить из-за WanGP Community License 2.0 |
| wan2gp-lora-manager | L1 | LICENSE отсутствует; только ссылка до получения письменного разрешения |
| wan2gp-queue-editor | L1 | LICENSE отсутствует; только ссылка до получения письменного разрешения |

У wanflow-ui нет настроенного публичного upstream: считать его сопровождаемым нами форком. media_gallery.py — input-slot widget, а не Media Center/indexer; Media Center строится как отдельный модуль. models_manager — bundled-плагин DeepBeepMeep, uninstallable=false, не сторонняя зависимость из реестра.

### Уровни интеграции

- L1 — навигация/deep-link на существующую вкладку или страницу. Код плагина не импортируется и не копируется.
- L2 — вызов контрактного API в том же процессе. Требуются presence detection, version gate и graceful degradation.
- L3 — перенос/вендоринг кода при наличии разрешающей лицензии, атрибуции и notices.

## 4. Этапы реализации

### M0 — Stabilization (v0.1.1, P0)

**Цель:** подтвердить, что Studio v0.1 работает в живом WanGP без регрессий.

Задачи:
- Сверить ветку Studio с актуальным main; не смешивать с незакоммиченными пользовательскими файлами рабочего дерева.
- Установить и включить плагин через Plugin Manager; проверить маршрут /studio/ и register_web_app.
- Проверить WebAuthMiddleware, cookie и same-origin POST при запуске с --auth.
- Проверить каталог моделей, инспекцию, presets, settings JSON и LoRA inventory.
- Проверить submit через deepy.web_session()/WanGPSession и штатную очередь.
- Проверить SSE: прогресс, reconnect, terminal status, ошибки и отмену.
- Проверить ограничения активных задач и очистку истории.
- Зафиксировать baseline CPU/RAM в idle и во время генерации.
- Обновить документацию и сведения о bundled models_manager.

**Приёмка:** реальная генерация проходит; SSE показывает прогресс и финальный результат; cancel работает; ошибки не роняют Studio; отсутствие optional plugins не ломает базовые разделы; тесты не хуже baseline; diff ядра пуст.

### M1 — Media Center (v0.2, P1)

**Цель:** единая библиотека исходников и результатов генерации.

Задачи:
- Инвентаризировать четыре основных media roots WanGP, workspace folders и опциональные workflow outputs.
- Индексировать изображения, видео, аудио и .wgpworld.
- Использовать существующие парсеры metadata: media recording, video metadata, audio/video, audio metadata, World manifest/settings.
- Для .wgpworld читать ZIP_STORED manifest/settings, thumbnail и poster; показывать model type, dimensions, FPS, seed, segments и связанные exploration outputs.
- Переиспользовать Deepy thumbnail engine и endpoint /deepy_api/workspace_viewer/thumbnail; не создавать второй worker/cache.
- Создать Media API: пагинация, фильтры, детали, thumbnail, связи и пользовательские действия.
- UI: grid/list, search, filters, sort, lightbox, video/audio preview, metadata, copy prompt/settings, reuse, delete with confirmation, multi-select.
- Upload Center: drag/drop, multi-upload, validation, preview before submit, отправка в Generate/Workflow.
- SQLite допускается только как локальный индексный cache; инвалидация по path/size/mtime.
- Виртуализировать списки; API отдаёт страницы по 50–200 записей; оригиналы не загружать целиком в JS state.

**Приёмка:** все согласованные корни индексируются; .wgpworld распознаётся отдельным типом; World Explorer открывается штатно; видео не читается целиком ради карточек; память не растёт с прокруткой; Gallery работает без wanflow-ui и ImageSuite. Цель первого экрана — до 2 секунд на 10 тыс. записей после прогрева индекса.

### M2 — Workflow Integration (v0.3, P1/P2)

**Архитектурное решение:** вариант B — in-process HTTP facade + перенос canvas assets. Вариант A (deep-link/Gradio tab) остаётся fallback. Вариант C (вендоринг движка) допускается только если B технически неосуществим.

Задачи:
- B0, read-only: обнаружение wanflow-ui, version gate, node catalog, reusable blocks, чтение и валидация workflow.
- B1, execution: facade для GraphStore, run_graph, native queue, inputs, per-node events, SSE и cancel через cancel_check.
- B2, UI: перенести vanilla editor.js assets; заменить Gradio hidden-button bridge на Studio facade; сохранить исходную schema и semantics.
- Изолировать все приватные связи (_ui_local, _process_inline_queue, server_config, prompt enhancer internals) в workflow_compat.py.
- Добавить GET /studio/api/environment; показывать capability/state каждого optional plugin.
- При несовместимости или ошибке facade — контролируемая деградация к варианту A, без падения Studio.

**Приёмка:** графы читаются и сохраняются без потери; run использует существующий run_graph и native queue; cancel передаётся в cancel_check; отсутствие wanflow-ui отображает not_installed; остальные разделы продолжают работать; второго runtime нет.

### M3 — Resource Center (v0.4, P2)

Задачи:
- Источники: WanGPSession callbacks, существующие MMGP metrics, psutil process/system RAM; NVML optional для GPU utilization, VRAM, temperature, power и fan.
- Показывать текущую модель/задачу, queue overview, step timing, speed и ETA только при наличии достоверных данных.
- status-pro использовать как ориентир по источникам, но не делать runtime dependency: UI-инъекции и private wrappers не использовать.
- Не делать собственный polling-heavy collector и не управлять offloading.

**Приёмка:** telemetry read-only; отсутствие NVML показывает unavailable, не ломая генерацию; polling ограничен; метрики не создают заметной CPU/RAM нагрузки; источник и точность каждого показателя задокументированы.

### M4 — Model Center (v0.5, P2)

Задачи:
- Единый каталог WanGP models, definitions, metadata/schema, file availability и capabilities.
- Native defaults, presets/profiles и advanced settings JSON.
- LoRA inventory через поддерживаемый WanGP API.
- models_manager использовать через L2; удаление файлов и другие destructive operations оставить его штатному UI.
- lora-manager и queue-editor без лицензии — только L1 deep-links.
- Живая очередь Studio работает через WanGPSession, не через queue-editor.

**Приёмка:** основные функции доступны без Tophness plugins; код без лицензии не импортируется и не копируется; каталог и schema берутся из runtime, а не статического списка.

### M5 — Editing Suite (v0.6, P2/P3)

Задачи:
- ImageSuite — L1: deep-link и явный SendTo выбранного изображения/frame.
- Не копировать ImageSuite code и не встраивать его как собственный компонент.
- Результат возвращается в Media Center через поддерживаемый файловый/metadata flow.
- При отсутствии/отключении показывать dependency state и ссылку на Plugin Manager.

**Приёмка:** передача медиа выполняется явным действием пользователя; Studio полноценно работает без ImageSuite; вендоринга кода нет.

### M6 — Workflow interoperability (v0.7, P3)

Задачи:
- Канонический внутренний формат — существующая schema wan2gp-wanflow-ui v1.
- Добавить versioning, import/export, validation, migrations и сохранение неизвестных узлов.
- ComfyUI JSON — только adapter import/export; не вводить третий внутренний формат.
- Неподдерживаемые узлы не отбрасывать молча: opaque preservation или отчёт о несовместимости.

**Приёмка:** один внутренний формат; round-trip tests проходят; unknown nodes диагностируются и сохраняются; migration tests покрывают старые workflow.

### M7 — Production v1.0 (P3)

Задачи:
- Итоговые разделы: Dashboard, Generate, Workflow, Media Center, Image Editor, Models, Queue, Resource Center, Settings.
- Unit/API/frontend tests; SSE reconnect; cancellation; workflow execution; media/World fixtures; plugin absence/update; NVML absence.
- Long-session и memory-growth tests.
- Документация install/upgrade, user guide, workflow/media guide, plugin integration, compatibility matrix, troubleshooting, attribution/licenses.

**Приёмка:** обязательные сценарии зелёные; optional plugins graceful; runtime/queue/offloading не дублируются; ядро не меняется; UI соответствует UI Concept.

## 5. Capability registry и graceful degradation

Единый GET /studio/api/environment сообщает версию ядра, auth, плагины, версии, capabilities, integration level и reason.

Состояния: available, not_installed, disabled, incompatible, unlicensed, unavailable.

Обнаружение:
1. Загруженные plugins через Plugin Manager.
2. Presence probe каталога для установленных, но выключенных.
3. Контрактные методы — только для контролируемых компонентов.

Никаких сторонних импортов на module import. Навигация строится по capabilities; недоступный раздел показывает причину и разрешённое действие.

## 6. UI и производительность

- Dark, restrained, professional; workflow-first; canvas в приоритете.
- Статические CSS surfaces, без динамических градиентов, постоянного blur, WebGL-декора и animation loops.
- Lazy-load разделов; virtualized lists; thumbnails только для видимой области; bounded caches/SSE/history.
- Не держать полные изображения/видео в JS state или PIL/video objects в долгоживущих backend objects.
- Не добавлять frontend framework, worker или сервер без доказанной необходимости.
- Целевая машина: RTX 5070 Ti Laptop 12 GB, 32 GB RAM, Windows 11. Численные бюджеты CPU/RAM установить по baseline, а не обещать без измерений.

## 7. Последовательность и спринты

| Спринт | Содержание | Результат |
|---|---|---|
| Sprint 0 | M0: live smoke, auth, generation, SSE, cancel, baseline | зелёная v0.1.1 |
| Sprint 1 | M1 discovery: roots, parsers, World fixtures, thumbnails, Media API | проверенный индексатор |
| Sprint 2 | M1 Gallery UI + upload + performance | Media Center v0.2 |
| Sprint 3 | M2 B0/B1 facade spike, run/cancel tests | доказанный workflow bridge |
| Sprint 4 | M2 B2 canvas + capability fallback | Workflow v0.3 |
| Sprint 5 | M3 telemetry read-only | Resource Center v0.4 |

M3 можно вести параллельно M2, если не затрагивать workflow/runtime internals.

## 8. Definition of Done

Этап закрыт только если есть реальная проверка в WanGP; тесты новой логики; обработка ошибок и несовместимостей; проверка без optional plugins; измерение CPU/RAM; отсутствие второго runtime/queue/allocator; соблюдение лицензий; пустой diff ядра; обновлённая документация и compatibility matrix.

## 9. Основные риски

| Риск | Мера |
|---|---|
| wanflow-ui без upstream | считать сопровождаемым форком; baseline, tests, THIRD_PARTY_NOTICES |
| приватные API меняются | workflow_compat.py, version gate, smoke tests |
| plugins обновляются независимо | capability detection, contract tests, graceful fallback |
| Tophness без LICENSE | только L1 до разрешения |
| Community License ImageSuite | только L1; юридическая проверка перед hosted/paid use |
| большие media collections | pagination, virtualization, bounded cache |
| дублирование MMGP/status-pro | Resource Center только читает источники |
| неполные metadata | штатные parsers и fixtures |

## 10. Вне scope

- Переписывание WanGP runtime.
- Второй backend/server или генерационная очередь.
- Собственный allocator/offloading.
- Полноценный ComfyUI runtime.
- Вендоринг ImageSuite, lora-manager или queue-editor.
- Новая медиа-БД/thumbnail service без измеренной необходимости.

**Принцип:** расширять WanGP, а не строить параллельную экосистему внутри него.
