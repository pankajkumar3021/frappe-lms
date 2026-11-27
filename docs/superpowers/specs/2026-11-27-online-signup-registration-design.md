# Online student sign-up with Google, registration form, class-filtered courses

Date: 2026-11-27. Status: draft for approval (follow-up page added 2026-11-27).

## Intent

Gradex Classes wants online students to join on their own. Today every student is
created by hand (imported from a sheet, enrolled into a branch batch, given Raven chat).
An online student should instead:

1. sign up with their Gmail account (Google sign-in),
2. fill a one-time registration form: name, contact number, class, city, and whether
   they want Online courses, Classroom courses, or both,
3. land on the course list, already filtered to their class, showing free and paid
   courses.

Online students get no Raven chat. A student who ticks Classroom is a lead: the
Gradex team follows up with them (call, visit, demo) and records how it went.

## Goals

- Self sign-up with Google for new users, with no staff action needed.
- A registration form every self-signed-up student must complete before using the LMS.
- A Student Registration record per student that the team works through to follow up
  on Classroom interest, with a status, an owner and notes.
- A Class filter on the Courses page, driven by course tags, preset to the student's
  class.

## Non-goals

- No class field on LMS Course. A course's class is a tag ("Class 10").
- No automatic batch enrollment, and no Raven profile, for self-signed-up students.
- No payment gateway setup. Paid courses show their price as today; buying one works
  only once a gateway is configured on the site (none is on prod now).
- No email/password self sign-up changes; Google is the path we support. The existing
  email sign-up form stays as it is.
- No SMS/OTP check on the contact number.

## Anti-goals (a failure even if it works)

- A self-signed-up student ends up in Raven (a Raven User profile, the Raven User role,
  or a workspace or channel membership).
- The existing, hand-imported students or staff are forced through the registration
  form.
- A student can read the team's follow-up notes or other students' registrations.
- Filtering "Class 1" also shows "Class 10", "Class 11 PCM", "Class 12 PCB" courses.

## Constraints from the codebase and site

- Google sign-in already exists on prod (Social Login Key "Google", enabled) with
  Sign ups set to **Deny**. Switching it to **Allow** is a site setting, done at deploy.
  Website Settings must also not have `disable_signup` set.
- New users get the LMS Student role on insert (`lms.lms.user.add_lms_student_role`).
  Raven access only comes from a batch enrollment (raven_integration rules) or the
  Admin role (`lms.lms.raven_chat.provision_chat_admin`). A user who only enrolls in
  courses gets no Raven profile. Nothing here may change that.
- User already has `mobile_no` (core), and `city` and `branch` (custom fields in
  `lms/install_data/custom_field.json`).
- `LMS Course.tags` is a comma-separated string (`"Class 10, Science"`; the UI splits on
  `", "`). `get_courses` in `lms/lms/utils.py` only matches tags through the title
  search (a `like`), so a tag filter must match whole tags.
- The SPA navigation guard is `guardNavigation` in `frontend/src/router.js`.
- The Gradex team who follow up are mostly Website Users without desk access (Admin
  role holders, Course Creators). Only System Managers and Moderators reliably reach
  the desk.
- Access rules live in `lms/lms/permissions.py`; translations use `_()` / `__()`;
  schema changes ship with migrate (see AGENTS.md).

## Approaches considered

- **A. Answers stored on the User profile.** New User fields for class and
  Online/Classroom; the team uses a filtered User list in the desk. Smallest change, but
  nowhere to record follow-up, and staff and students share the list.
- **B. A Student Registration record per sign-up (chosen by the user).** A new DocType
  holds the answers plus follow-up fields. Phone, city and class are also copied to the
  User so the rest of the LMS can use them. Follow-up has a proper home and conversion
  can be counted.
- (Dropped) Frappe CRM leads: CRM is not installed on the site, and it would be a second
  app to run for one form.

## Design

### 1. Student Registration DocType (`lms/lms/doctype/student_registration/`)

One record per user. Named by the user's email (`autoname: field:user`), so there can
only be one.

Fields:

| Field | Type | Notes |
|---|---|---|
| user | Link User, reqd, unique, read-only after insert | |
| full_name | Data, reqd | |
| contact_number | Data (Phone), reqd | 10-digit Indian mobile, stored as `+91XXXXXXXXXX` |
| student_class | Select, reqd | Class 1 … Class 10, Class 11 PCM, Class 11 PCB, Class 12 PCM, Class 12 PCB |
| city | Select, reqd | Delhi, Noida, Muzaffarpur, Motipur |
| wants_online | Check | |
| wants_classroom | Check | at least one of the two must be set |
| follow_up_status | Select | New, Contacted, Joined, Not interested. Default New |
| assigned_to | Link User | the team member following up |
| follow_up_notes | Small Text | |
| registered_on | Datetime, read-only | set on insert |

The class list is defined once (a Python constant, also returned to the frontend by the
API) so the form, the DocType options and the course tags agree.

Permissions (DocType): System Manager full; Moderator and the Admin role read/write,
no create, no delete (they use the Registrations page in section 5). No permission for LMS Student: students never read the DocType
through REST, so they never see notes. Desk list view default filter:
`wants_classroom = 1, follow_up_status = New`, sorted by `registered_on` desc.

### 2. Server API (`lms/lms/registration.py`)

- `get_registration_state()` (whitelisted, logged-in): returns
  `{needs_registration: bool, classes: [...], cities: [...], prefill: {full_name, contact_number}}`.
  `needs_registration` is true only when **all** hold:
  - the user is a Website User,
  - their only LMS role is LMS Student (no Moderator, Course Creator, Batch Evaluator,
    Admin or other staff role, reusing the staff role list in `permissions.py`),
  - they have no Student Registration,
  - they have no LMS Batch Enrollment (this keeps the imported classroom students out).
- `submit_registration(full_name, contact_number, student_class, city, wants_online, wants_classroom)`
  (whitelisted, POST, logged-in, rate-limited): validates, creates the Student
  Registration for `frappe.session.user` only (no user argument), and copies onto the
  User: `full_name` (into first/last name), `mobile_no`, `city`, and the class into a
  new User custom field `student_class` (Data, so it can be read without a join). A
  second call for the same user returns an error ("already registered"); editing later
  is out of scope for students.
- The method never touches roles, batches or Raven.

### 3. Registration page (SPA)

- New route `Registration` at `/lms/registration`, page `frontend/src/pages/Registration.vue`.
- The guard in `router.js`: for a logged-in user, ask `get_registration_state` once per
  app load (cache it like `setupChecked`). If `needs_registration`, send every route
  except `Registration` to it. After a submit, clear the cache and go to
  `Courses` with `?class=<their class>`.
- The form: full name (prefilled from Google), contact number (+91 prefix shown),
  class (dropdown), city (dropdown), "I'm interested in" with two checkboxes, Online
  and Classroom. Inline validation messages; all strings through `__()`.
- If the guard check fails (network), fail open, as the setup check does.

### 4. Class filter on Courses

- Courses page (`frontend/src/pages/Courses/Courses.vue`) gets a **Class** dropdown next
  to the category filter, with the fixed class list. Its value goes into the URL as
  `?class=` like `category` does.
- Default: when the URL has no `class`, use the logged-in user's `student_class` (from
  the user resource; add it to the fields `get_user_info` returns). A "All classes"
  option clears it.
- Server: `update_course_filters` in `lms/lms/utils.py` turns `filters["class"]` into a
  whole-tag match on `LMS Course.tags`: the tag equals the value, or starts with
  `"<value>, "`, ends with `", <value>"`, or contains `", <value>, "`. Validate the
  value against the class list first.
- Free and paid courses show together; paid ones already show their price.

### 5. Registrations page for the team (SPA)

The follow-up team (Admin role holders such as Anjali, Chandan and Rahul, and
Moderators) are Website Users without desk access, so the list lives in the LMS.

- New route `Registrations` at `/lms/registrations`, page
  `frontend/src/pages/Registrations.vue`, plus a sidebar item shown only to these roles
  (`lms/lms/sidebar.py`).
- Who may use it: Moderator, Admin role, System Manager. One check,
  `can_manage_registrations(user)` in `lms/lms/permissions.py`, used by every method
  below and by the DocType's `has_permission` hook, so the rule lives in one place.
- List: name, class, city, Online/Classroom, contact number (a `tel:` link so a tap
  dials on a phone), registered on, status, assigned to. Filters: status (default New),
  Classroom only (default on), class, city, assigned to (with "Me"). Newest first,
  paged.
- Opening a row shows the details with editable status, assigned to (team members
  only) and notes. Saving updates the record.
- Server (whitelisted, in `lms/lms/registration.py`):
  `get_registrations(filters, start, page_length)` returning rows and a count,
  `update_registration(name, follow_up_status, assigned_to, follow_up_notes)` which
  changes only those three fields, and `get_registration_team()` for the assignee
  picker. Each checks `can_manage_registrations`.
- The desk list stays available to System Managers as a fallback.

### 6. Turning it on (site settings, at deploy, not code)

- Social Login Key "Google": Sign ups → Allow.
- Check Website Settings `disable_signup` is off.
- Tag the existing courses with their class, using the exact class names.

## Tests

- Python (`lms/tests/test_registration.py`): needs_registration for a fresh student,
  false for staff, for a user with a batch enrollment, and after submit; submit
  validates the phone, class, city and the at-least-one checkbox; submit copies to
  User; a second submit fails; a student cannot read Student Registration via
  `frappe.client.get` / `get_list`; after submit the user has no Raven User role
  (when Raven is installed). Class tag filter: "Class 1" does not match "Class 10" or
  "Class 11 PCM"; it does match "Class 1" alone, first, middle and last in the list.
- Python: a student and a Course Creator get a permission error from
  `get_registrations` and `update_registration`; an Admin role holder and a Moderator
  succeed; `update_registration` ignores any field other than the three it allows.
- Vitest: the Registrations page filters and the save; the sidebar item shows only for
  the team roles.
- Vitest: the Registration form's validation and submit; the guard sends a user who
  needs registration to it and lets others through; the Class dropdown sets the query.

## Calls made by Claude (please check)

- The registration gate applies only to Website Users whose only role is LMS Student and
  who have no batch enrollment. The 12 imported students and all staff skip it.
- Classes: Class 1–10, Class 11 PCM/PCB, Class 12 PCM/PCB (matching the branch batches).
- Contact number: 10-digit Indian mobile only.
- Students can't edit their registration after submitting; the team edits it in the desk.
- Online and Classroom are checkboxes; a student may tick both. All students land on the
  course list afterwards.
- The team works the follow-up list on a Registrations page in the LMS (the user chose
  this over desk-only). Moderators, Admin role holders and System Managers can use it;
  Course Creators (teachers) cannot.

## Left to the builder

- Exact layout and copy of the registration page, within the existing frappe-ui style.
- Whether `student_class` on User is shown on the profile page.
- Rate-limit numbers for `submit_registration`.
