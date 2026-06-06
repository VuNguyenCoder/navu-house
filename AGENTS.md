# AGENTS

## Project snapshot

- Stack: Django 6, PostgreSQL, Redis, Bootstrap 5, Docker Compose, Ansible.
- Main app flow: rooms -> subscriptions -> monthly usage -> billing.
- Languages: English and Vietnamese.

## Core business rules

### Room

- `Room.type` supports:
  - `enclosed`
  - `unenclosed`
  - `rest`
- `Unenclosed` rooms can link to one `Rest` room through `linked_restroom`.
- Latest electricity and water readings on `Room` are operational baselines and include update metadata:
  - time
  - source
  - linked usage
  - updated user

### Subscription

- Only one enabled subscription is allowed per room at a time.
- `Subscription` stores pricing snapshot fields and `tenant_count`.
- `Subscription` also stores `image_paths`.

### Usage

- `Usage.status` uses:
  - `unpaid`
  - `paid`
- `paid` usage records are locked:
  - form fields are disabled
  - update is blocked
  - delete is blocked
- New `Usage.tenant_count` default:
  - from latest usage of the same subscription if it exists
  - otherwise from `Subscription.tenant_count`
- Saving a usage record updates `Subscription.tenant_count` to the current usage value.

### Restroom allocation

- A `Rest` room can have its own usage record.
- `Unenclosed` subscriptions linked to that restroom receive allocated restroom electricity/water cost.
- Allocation is based on total linked tenant count for the period.
- Dashboard rules:
  - `Grand total amount`, electricity revenue, water revenue, and usage status exclude `Rest` room usage to avoid double count.
  - `Total electricity consumed` and `Total water consumed` still reflect physical system-wide consumption, including restroom usage.

## UI conventions

- Global layout:
  - top navbar is sticky
  - desktop sidebar is sticky
  - breadcrumb is sticky and visually elevated
- Footer shows:
  - `Copyright by VuNguyenCoder. Build time: <build_time>`
- Focus style for normal inputs/selects:
  - black border
  - thicker border
  - no Bootstrap glow

## Reusable components

### Numeric input

- Component path:
  - `templates/components/numeric_input/main.html`
- Component docs:
  - `templates/components/numeric_input/README.md`
- Use for grouped-number inputs with optional `Clear`, `+`, `-`.
- `step_value` default is `1`.
- Money fields in this project usually use `step_value=1000`.
- If the field is disabled:
  - spinner controls are hidden
  - input returns to standalone border/radius shape
- Other scripts should interact with the underlying input by `id` or `name`, not by button internals.

## Media and uploads

- Room images:
  - `media/rooms/<room_name>/...`
- Subscription images:
  - `media/subscriptions/<subscription_id-or-draft>/...`
- Usage meter images:
  - `media/usages/<subscription_id>/<YYYY-MM>/...`

## Dashboard behavior

- Home dashboard month selection uses `Settings.payment_period`.
- Default period rule:
  - before `payment_period` day -> previous month
  - from `payment_period` day onward -> current month
- Available month options:
  - previous 12 months through current month
  - plus next 2 months
  - ordered newest first

## Settings

- Singleton model: `Settings`
- Currently used for:
  - `payment_period`

## Deployment notes

- Main deploy playbook:
  - `ansible/deploy.yml`
- Remote deploy uses Docker Compose override rendered by Ansible.
- HTTPS currently uses reverse-proxied nginx in deploy flow.
- Footer `build_time` comes from the last Ansible deploy run:
  - Ansible captures timestamp in `Asia/Ho_Chi_Minh`
  - passes it as `APP_BUILD_TIME` to the web container

## Translation workflow

- If only `msgstr` changes:
  - rebuild `.mo`
- If source text (`msgid`) changes:
  - run `makemessages`
  - update `.po`
  - rebuild `.mo`

Typical commands:

```bash
/Users/anhvu/external/navu-house/.venv/bin/python manage.py makemessages -l vi
msgfmt locale/vi/LC_MESSAGES/django.po -o locale/vi/LC_MESSAGES/django.mo
```

## Safe verification commands

Use these after template/form/view changes:

```bash
python3 -m compileall apps/main config
/Users/anhvu/external/navu-house/.venv/bin/python manage.py check
```

## Editing guidance

- Prefer preserving existing Bootstrap-based patterns.
- Avoid reintroducing Japanese locale support unless explicitly requested.
- Be careful with `Rest` room billing logic; it is easy to double count totals.
- If updating numeric input behavior, also review:
  - disabled-state behavior
  - focus styling
  - grouped-number parsing/formatting
  - JS listeners that read values by field `id`
