# Online Sign-up, Registration Form and Class Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Students sign up with Google, fill a one-time registration form, land on courses filtered to their class; the team follows up Classroom leads on an LMS page.

**Architecture:** A `Student Registration` DocType holds each student's answers and the team's follow-up fields. `lms/lms/registration.py` owns the student-facing and team-facing whitelisted methods; `lms/lms/permissions.py` owns the one access check. The SPA gets a router gate to `/lms/registration`, a Class dropdown on Courses, and a `/lms/registrations` team page.

**Tech Stack:** Frappe (Python 3.14), Vue 3 + frappe-ui, Vitest, Frappe IntegrationTestCase.

**Spec:** `docs/superpowers/specs/2026-11-27-online-signup-registration-design.md`

## Global Constraints

- Classes, exactly and in this order: `Class 1` … `Class 10`, `Class 11 PCM`, `Class 11 PCB`, `Class 12 PCM`, `Class 12 PCB`.
- Cities, exactly: `Delhi`, `Noida`, `Muzaffarpur`, `Motipur`.
- Follow-up statuses: `New` (default), `Contacted`, `Joined`, `Not interested`.
- Contact number: 10-digit Indian mobile (first digit 6–9), stored as `+91XXXXXXXXXX`.
- Team roles: `Moderator`, `Admin` (`CHAT_ADMIN_ROLE`), `System Manager`. Course Creators are not team.
- Nothing in this feature grants roles, creates batch enrollments or touches Raven.
- Strings through `_()` (Python) and `__()` (frontend). Ruff: tabs, line length 110.
- Python tests create the users they act as (`BaseTestUtils._create_user` in `lms/lms/test_helpers.py`).
- Run backend tests from `frappe-bench/`: `bench --site learning.test run-tests --app lms --module <module>`.

## Review Focus

1. A contact number typed as `98765 43210`, `+91 9876543210`, `09876543210` or `919876543210` should be accepted and stored as `+919876543210`; `12345` or `5876543210` rejected. → test in Task 2.
2. A student submitting twice (two tabs, double click) gets a clear "already registered" error, not a duplicate-key traceback. → test in Task 2.
3. The gate must never loop: a user who needs registration and opens `/lms/registration` stays there; when the state call fails the user is let through. → test in Task 5.
4. A course tagged `Class 10, Science` must not show for `Class 1`; tags with odd spacing (`Class 1 ,Maths`) still match `Class 1`. → test in Task 4.
5. `update_registration` with an `assigned_to` who is not team, or a status outside the list, is refused. → test in Task 3.

---

### Task 1: Student Registration DocType, constants and access check

**Files:**
- Create: `lms/lms/doctype/student_registration/{__init__.py,student_registration.json,student_registration.py,test_student_registration.py}`
- Create: `lms/lms/registration.py` (constants only in this task)
- Modify: `lms/lms/permissions.py` (after `is_chat_student`), `lms/hooks.py` (`has_permission`, `permission_query_conditions`), `lms/tests/docperms.json` (regenerate the baseline entry for the new DocType)

**Interfaces:**
- Produces: `lms.lms.registration.CLASSES: tuple[str, ...]`, `CITIES`, `FOLLOW_UP_STATUSES`; `lms.lms.permissions.REGISTRATION_TEAM_ROLES = ("Moderator", CHAT_ADMIN_ROLE, "System Manager")`; `can_manage_registrations(user: str | None = None) -> bool`; DocType `Student Registration` with the fields in spec §1 (fieldnames: `user, full_name, contact_number, student_class, city, wants_online, wants_classroom, follow_up_status, assigned_to, follow_up_notes, registered_on`), `autoname: field:user`, module LMS. Select options are the constants joined by `\n`.

- [ ] **Step 1: Write failing tests** in `test_student_registration.py` (class extends `BaseTestUtils`):
  - `test_requires_online_or_classroom`: inserting with both checks 0 raises `frappe.ValidationError`.
  - `test_registered_on_set_and_status_defaults_new`.
  - `test_doctype_options_match_constants`: `frappe.get_meta("Student Registration").get_field("student_class").options.split("\n") == list(CLASSES)`; same for city and status.
  - `test_can_manage_registrations`: True for users with Moderator, Admin, System Manager; False for LMS Student and Course Creator.
  - `test_student_cannot_read_registrations`: as a student, `frappe.get_list("Student Registration")` returns `[]` and `frappe.get_doc(...).check_permission("read")` raises `frappe.PermissionError` — including on their own record.
- [ ] **Step 2:** Run `bench --site learning.test run-tests --app lms --module lms.lms.doctype.student_registration.test_student_registration` → FAIL (DocType missing).
- [ ] **Step 3:** Create the DocType JSON (perms: System Manager full; Moderator and Admin read/write/report, no create/delete), the controller (`validate` enforces one of the checks; `before_insert` sets `registered_on = now_datetime()`), the constants, and `can_manage_registrations`. Wire `has_permission["Student Registration"]` and `permission_query_conditions["Student Registration"]` to functions in `permissions.py` that return allow / `""` for team and deny / `"1=0"` otherwise. Run `bench --site learning.test migrate`.
- [ ] **Step 4:** Run the module tests → PASS. Run `--module lms.tests.test_docperm_snapshot`; update `lms/tests/docperms.json` with the new Moderator grant and re-run → PASS.
- [ ] **Step 5:** Commit `feat(registration): Student Registration record and team access check`.

### Task 2: Student-facing API and User fields

**Files:**
- Modify: `lms/lms/registration.py`, `lms/install_data/custom_field.json` (User `student_class`, Data, read-only, insert_after `city`), `lms/lms/api.py:get_user_info`
- Test: `lms/tests/api/test_registration_api.py`

**Interfaces:**
- Consumes: Task 1 constants and DocType.
- Produces: `get_registration_state() -> dict` with keys `needs_registration: bool, classes: list[str], cities: list[str], prefill: {full_name: str, contact_number: str}`; `submit_registration(full_name: str, contact_number: str, student_class: str, city: str, wants_online: bool, wants_classroom: bool) -> dict` returning `{"student_class": str}`; `normalize_mobile(value: str) -> str` (raises `ValidationError`); `get_user_info()` adds `student_class` and `can_manage_registrations`.

- [ ] **Step 1: Write failing tests:**
  - `test_fresh_student_needs_registration` → `needs_registration is True`.
  - `test_staff_do_not_need_registration`: Course Creator, Moderator, Admin role, System User each → False.
  - `test_batch_enrolled_student_does_not_need_registration`.
  - `test_submit_creates_record_and_copies_to_user`: after submit, User has `mobile_no == "+919876543210"`, `city`, `student_class == "Class 10"`, `full_name` updated; state now False.
  - `test_normalize_mobile` with the Review Focus 1 table (accept 4 forms → `+919876543210`; reject `12345`, `5876543210`).
  - `test_rejects_unknown_class_and_city` and `test_rejects_neither_mode`.
  - `test_second_submit_says_already_registered`: second call raises `frappe.ValidationError` whose message contains "already registered".
  - `test_submit_grants_no_roles`: roles before == roles after; if `frappe.db.exists("DocType", "Raven User")`, no Raven User row for the user.
  - `test_get_user_info_has_student_class`.
- [ ] **Step 2:** Run `--module lms.tests.api.test_registration_api` → FAIL.
- [ ] **Step 3:** Implement. `needs_registration` per spec §2 (Website User; `frappe.get_roles` ∩ `CHAT_STAFF_ROLES` empty; no Student Registration; no LMS Batch Enrollment with `member = user`). `submit_registration` is `@frappe.whitelist(methods=["POST"])` with `@rate_limit(limit=5, seconds=60)`, acts only on `frappe.session.user`, refuses Guest, checks existence first for the friendly error, inserts with `ignore_permissions=True` (justify with a `# nosemgrep` comment like others in the repo), then `frappe.db.set_value("User", ...)` for `first_name`/`last_name` (split on the first space), `mobile_no`, `city`, `student_class`. Add `student_class` to the custom field JSON; run migrate.
- [ ] **Step 4:** Run tests → PASS. Run `--module lms.tests.test_install` → PASS (update its expected field list if it enumerates User fields).
- [ ] **Step 5:** Commit `feat(registration): registration state and submit for new students`.

### Task 3: Team API

**Files:**
- Modify: `lms/lms/registration.py`
- Test: `lms/tests/api/test_registration_team_api.py`

**Interfaces:**
- Consumes: `can_manage_registrations`, constants.
- Produces: `get_registrations(filters: dict | None = None, start: int = 0, page_length: int = 20) -> {"rows": list[dict], "count": int}` — allowed filter keys `follow_up_status, wants_classroom, student_class, city, assigned_to` (others ignored), ordered `registered_on desc`, row fields `name, full_name, contact_number, student_class, city, wants_online, wants_classroom, follow_up_status, assigned_to, assigned_to_name, follow_up_notes, registered_on`; `update_registration(name: str, follow_up_status: str | None = None, assigned_to: str | None = None, follow_up_notes: str | None = None) -> dict`; `get_registration_team() -> list[{"value": email, "label": full_name}]` (enabled users holding a team role, excluding Administrator).

- [ ] **Step 1: Write failing tests:**
  - `test_student_and_course_creator_are_refused` for all three methods → `frappe.PermissionError`.
  - `test_admin_role_and_moderator_can_list` and the filter defaults: `{"follow_up_status": "New", "wants_classroom": 1}` returns only those, newest first; `count` matches.
  - `test_unknown_filter_keys_ignored` (e.g. `{"user": "x"}` doesn't filter or error).
  - `test_update_changes_only_three_fields`: passing extra kwargs via `frappe.call` with `contact_number` leaves it unchanged (method signature has no such param → TypeError is acceptable; assert value unchanged).
  - `test_update_refuses_bad_status_and_non_team_assignee` → `frappe.ValidationError`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement; each method starts with `if not can_manage_registrations(): frappe.throw(_("Not permitted"), frappe.PermissionError)`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(registration): list and update registrations for the follow-up team`.

### Task 4: Class tag filter on the course list

**Files:**
- Modify: `lms/lms/utils.py:update_course_filters` (around line 1652)
- Test: `lms/tests/test_course_class_filter.py`

**Interfaces:**
- Consumes: `CLASSES`.
- Produces: `get_courses(filters={"class": "Class 10", ...})` returns only courses whose tags contain that whole tag. Unknown class value → ignored (no filter), not an error.

- [ ] **Step 1: Write failing tests** with published courses tagged `"Class 1"`, `"Class 1, Maths"`, `"Maths, Class 1"`, `"Science, Class 1, Maths"`, `"Class 1 ,Maths"`, `"Class 10"`, `"Class 11 PCM"`, `""`: `test_class_1_matches_whole_tag_only` → exactly the first five; `test_class_10_does_not_match_class_1`; `test_unknown_class_ignored`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** In `update_course_filters`, pop `class`; if in `CLASSES`, find matching course names in Python (fetch `name, tags` where `tags like %value%`, then keep rows where `value in [t.strip() for t in tags.split(",")]`) and add `filters["name"] = ["in", names or [""]]`. Merge with any existing `name` filter by intersecting.
- [ ] **Step 4:** Run → PASS; also `--module lms.tests.api.test_api` → PASS.
- [ ] **Step 5:** Commit `feat(courses): filter the course list by class tag`.

### Task 5: Registration page and router gate

**Files:**
- Create: `frontend/src/pages/Registration.vue`, `frontend/src/composables/useRegistrationState.ts`
- Modify: `frontend/src/routes.js` (route `{ path: '/registration', name: 'Registration' }`), `frontend/src/router.js:guardNavigation`
- Test: `frontend/src/tests/Registration.test.ts`, `frontend/src/tests/registrationGuard.test.ts`

**Interfaces:**
- Consumes: `lms.lms.registration.get_registration_state`, `lms.lms.registration.submit_registration`.
- Produces: `useRegistrationState()` → `{ needsRegistration(): Promise<boolean>, markRegistered(): void }` caching one call per app load; failures resolve `false`.

- [ ] **Step 1: Write failing tests:**
  - Guard: logged-in user with `needs_registration: true` navigating to `Courses` → redirected to `{ name: 'Registration' }`; navigating to `Registration` → `next()` with no argument; state call rejects → `next()`; `needs_registration: false` → `next()`; guest → state never called.
  - Form: submit disabled until name, 10-digit number, class, city and at least one checkbox are set; on submit calls `submit_registration` with the values and then `router.replace({ name: 'Courses', query: { class: 'Class 10' } })`; server error message is shown.
  - a11y check like the other page suites.
- [ ] **Step 2:** `cd frontend && yarn vitest run src/tests/Registration.test.ts src/tests/registrationGuard.test.ts` → FAIL.
- [ ] **Step 3:** Implement. Gate runs after the setup check, only when `isLoggedIn`, and only for `userResource.data?.is_student`. After submit call `markRegistered()` and `userResource.reload()`. Page copy: heading "Tell us about yourself", label "I'm interested in", checkboxes "Online courses" and "Classroom courses", button "Continue".
- [ ] **Step 4:** Run → PASS; `yarn test` → PASS.
- [ ] **Step 5:** Commit `feat(registration): registration form new students fill before using the LMS`.

### Task 6: Class dropdown on Courses

**Files:**
- Modify: `frontend/src/pages/Courses/Courses.vue` (filters slot near line 50; query handling near lines 142, 250, 313)
- Test: `frontend/src/tests/CoursesClassFilter.test.ts`

**Interfaces:**
- Consumes: Task 4 `filters.class`; `userResource.data.student_class`; class list from `get_registration_state().classes` (fetch once; or reuse the composable's cached response).

- [ ] **Step 1: Write failing tests:** no `?class` + user `student_class: 'Class 10'` → resource filters include `class: 'Class 10'` and the dropdown shows it; `?class=Class 12 PCM` wins over the user's class; choosing "All classes" removes `class` from filters and sets `?class=all` in the URL so the default is not re-applied on reload; guest → no class filter.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement alongside `currentCategory` (a `currentClass` ref, `filters.value['class']`, and `class` in `filterKeys`). The `filtered` prop counts a class filter.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(courses): class dropdown that starts on the student's class`.

### Task 7: Registrations page for the team and sidebar link

**Files:**
- Create: `frontend/src/pages/Registrations.vue`, `frontend/src/components/RegistrationDetail.vue` (dialog)
- Modify: `frontend/src/routes.js` (`/registrations`, name `Registrations`), `frontend/src/utils/index.js:getSidebarItems` (item `Registrations`, icon `PhoneCall`, `to: 'Registrations'`, `condition: () => userResource.data?.can_manage_registrations`, in the group with Statistics), `lms/hooks.py:standard_sidebar_items` (`{"name1": "registrations", "is_standard": 1, "item_type": "Built-in"}`)
- Test: `frontend/src/tests/Registrations.test.ts`, extend the sidebar suite that covers `getSidebarLinks`

**Interfaces:**
- Consumes: Task 3 methods; `can_manage_registrations` from `get_user_info`.

- [ ] **Step 1: Write failing tests:** default load calls `get_registrations` with `{follow_up_status: 'New', wants_classroom: 1}`; changing status/class/city/"Assigned to me" re-queries with those keys; phone renders as `<a href="tel:+919876543210">`; saving the dialog calls `update_registration` with only `name, follow_up_status, assigned_to, follow_up_notes` and reloads; a user without `can_manage_registrations` opening the route is sent to `Home`; sidebar shows `Registrations` only when `can_manage_registrations` is true.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement with frappe-ui `ListView`/`Dialog` like `pages/QuizSubmissions.vue`. Route guard: a `beforeEnter` that checks `userResource.data?.can_manage_registrations`. Run migrate so the sidebar row is seeded; confirm the link shows for a Moderator on the dev site.
- [ ] **Step 4:** Run → PASS; full `yarn test` and `bench ... run-tests --app lms` → PASS. `pre-commit run --all-files` clean.
- [ ] **Step 5:** Commit `feat(registration): Registrations page for the follow-up team`.

### Task 8: Turn-on checklist

**Files:**
- Modify: the spec's §6 only if a step changed during the build.

- [ ] **Step 1:** On the dev site, end to end: allow sign-ups on the Google Social Login Key (or use a fresh test user if Google isn't configured on dev), sign in as a new user, confirm the redirect to `/lms/registration`, submit, land on Courses with the class preselected, confirm no Raven User role, then as a Moderator see the lead on `/lms/registrations` and set it to Contacted.
- [ ] **Step 2:** Put the prod switch-on steps in the PR description: deploy with `--migrate`; Social Login Key "Google" → Sign ups: Allow; Website Settings `disable_signup` off; tag courses with class names exactly as in Global Constraints.
- [ ] **Step 3:** Commit any fixes; open the PR into `develop` (no screenshots section).
