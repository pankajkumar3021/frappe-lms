# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project conventions (access checks, `__()`/`_()` translation, sibling-checking on bug fixes, PR and commit rules) are in `AGENTS.md`. This file covers how to run things and how the pieces fit together.

## Commands

This is a Frappe app. Nothing runs standalone: the backend needs a bench, and the frontend dev server talks to it.

**Backend (run from the bench directory, `frappe-bench/`)**
```bash
bench start                                              # web, workers, scheduler, socketio
bench --site learning.test migrate                       # after changing doctypes or patches
bench --site learning.test run-tests --app lms           # full Python suite
bench --site learning.test run-tests --app lms --module lms.lms.test_schedule_utils   # one module
bench --site learning.test run-tests --app lms --module lms.tests.api.test_api       # one module
```
Frappe's `run-tests` also takes `--test <name>` for a single test method; check `bench run-tests --help` on the installed version. Python tests must create the users they act as (see `lms/lms/test_helpers.py`).

**Frontend (from `frontend/`)**
```bash
yarn dev                                    # Vite dev server; proxies API calls to the bench
yarn build                                  # writes lms/public/frontend/ and copies index.html to lms/www/_lms.html
yarn test                                   # Vitest, single run
yarn vitest run src/tests/Quiz.test.ts      # one Vitest file
yarn test:watch
```
`lms/public/frontend/` and `lms/www/_lms.html` are build output and are not committed. The `build` script also builds a second entry, `vite.signup-select.config.js`.

**End-to-end (from the repo root)**
```bash
yarn test-local                             # Playwright with its UI
npx playwright test e2e/quiz.spec.ts        # one spec; needs the bench at http://lms.test:8000
```
`e2e/global.setup.ts` creates the authenticated state that the `e2e` project depends on.

**Lint and format**: pre-commit runs ruff (lint and format, tab indent, line length 110), prettier and eslint on staged files. Run `pre-commit run --all-files` to check everything. A hook that rewrites a file fails the commit, so stage the rewritten file and commit again.

**Environment**: Python 3.14 (`pyproject.toml`), Node 24 or later (root `package.json`). `frontend/node_modules/@framework/ui` must be a symlink to `apps/frappe/ui`. `package.json`'s `link:../../frappe/ui` only resolves from a bench, and `vite.config.js` throws with the fix command when it does not. Git worktrees hit this, so re-link by hand there.

## Architecture

**Two halves, one app.** The Frappe backend in `lms/` owns data, permissions and business rules. A Vue 3 SPA in `frontend/` (built with frappe-ui) is served at `/lms` through `lms/www/_lms.html`. The SPA calls the backend by dotted method path (`call('lms.lms.utils.get_lesson')`, `createResource({ url: 'lms.lms.api.get_badges' })`), so the method name is the contract between the two halves. A grep for a method name finds both ends.

**Backend layers**
- `lms/lms/doctype/` (72 DocTypes): controllers hold validation and state changes. The lesson controller is `lms/lms/doctype/course_lesson/course_lesson.py`, with its tests beside it.
- `lms/lms/api.py`: whitelisted entry points for writes and most actions.
- `lms/lms/utils.py`: read paths for lists and pages (course outlines, lessons, quizzes, progress). The frontend reads most pages through these.
- `lms/lms/permissions.py`: the single access-control layer for courses, batches, lessons, assessments and lesson media. Permission hooks in `lms/hooks.py` (`permission_query_conditions`, `has_permission`, `has_website_permission`) route to it, so a check written inline in one place drifts from the rest.
- `lms/hooks.py` wires the rest: `doc_events`, `scheduler_events`, `override_doctype_class`, `override_whitelisted_methods`, website routes, and `after_migrate`. A behavior change that looks like it belongs in one controller may be wired elsewhere; grep `hooks.py` first.
- `lms/patches.txt` plus `lms/patches/`: data migrations for existing sites. A schema change that affects live data needs a patch entry.

**Lesson content is EditorJS blocks.** A lesson's `content` is a JSON block list. Quizzes, assignments and programming exercises are embedded as blocks, and the content is the source of truth. `lms/lms/lesson_assessments.py` reads the blocks into `Course Lesson.assessments`, which is a queryable index derived from them. The lesson save and the backfill patch both use that one reader, so changes to the block shape must go through it. Legacy `body` macros (`lms/lms/md.py`) are still honored.

**Frontend layers**
- `frontend/src/routes.js` is the route table, separate from `router.js` so tests can load the real table. `router.js` adds the navigation guard: it checks setup state through `lms.lms.onboarding.get_setup_state` and the user's persona before a page loads.
- Forms such as course, chapter, batch and enrollment open as child routes, handled by `composables/useFormRoute.ts`. Closing a form pops history only if the form itself pushed the entry, so a deep link is not broken.
- `frontend/src/pages/` holds one component per route. Shared pieces live in `components/`, shared logic in `composables/`, and session, user and settings state in `stores/` (Pinia).
- Real-time updates go through `socket.io-client` (`src/socket.js`); the app provides `$socket`, `$user` and `$allUsers` to components.
- `frontend/src/tests/` holds about 250 Vitest suites, many of them mount tests and a11y checks; `setupFiles` registers the `v-safe-html` directive the way `main.js` does.

**Concurrency.** Enrollment, lesson locking and other counts that must not race use `lms/lms/locking.py` (`locked_count`, `locked_get_all`). They take row locks, so call them after the transaction's own insert and filter on indexed columns, or they can deadlock.

**Tests map to the layers.** `lms/tests/` and the colocated `lms/lms/test_*.py` hold server tests, with `lms/tests/security/` covering access rules and `lms/tests/api/` covering whitelisted methods. `e2e/` holds Playwright flows for course creation, batches and quizzes.
