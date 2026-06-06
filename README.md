# Navu House

Navu House is a Django-based room rental management application for small boarding houses and rental buildings. It helps operators manage rooms, subscriptions, monthly utility usage, vehicles, pricing templates, and billing-related data in one place.

## Highlights

- Room management with image uploads
- Subscription management for each room
- Monthly usage records for electricity and water
- Real-time total amount calculation with billing breakdown
- Shared price template for default pricing
- Vehicle management linked to subscriptions
- English and Vietnamese interface
- Mobile-friendly Bootstrap 5 UI
- Docker-based deployment
- Ansible-based remote deployment and backup automation

## Core Concepts

### Room

A room stores:

- Room name
- Description
- Room images
- Latest electricity reading
- Latest water reading

### Subscription

A subscription represents one rental contract for one room.

It stores:

- Room
- Rental start date
- Start electricity reading
- Start water reading
- Deposit amount
- Price snapshot
- Contact phone number
- Contact email
- Status

Only one enabled subscription is allowed per room at a time.

### Usage

A usage record stores monthly billing data for a subscription:

- Billing month
- Tenant count
- Price snapshot
- Latest electricity reading
- Latest water reading
- Meter images

The application calculates the total amount in real time using:

- Room price
- Electricity consumed × electricity price
- Water consumed × water price
- Internet price
- Cleaning price × tenant count
- Laundry price × tenant count

For the first usage record of a subscription, the baseline comes from the subscription start readings.

### Vehicle

Vehicles are attached to subscriptions instead of rooms, which makes the data belong to the correct tenant contract.

## Technology Stack

- Python 3.12
- Django 6
- PostgreSQL
- Redis
- Bootstrap 5
- Docker / Docker Compose
- Ansible

## Local Development

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Review:

- `config/.env`

### 3. Run with Docker Compose

```bash
docker compose up -d --build
```

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Start the app if you are not using Docker for the web process

```bash
python manage.py runserver
```

## Deployment

This project includes an Ansible-based deployment flow in [`ansible/README.md`](/Users/anhvu/external/navu-house/ansible/README.md:1).

The deployment setup currently supports:

- Docker installation on the remote host
- Project sync to the remote server
- Environment-specific Docker Compose override
- Container startup with `docker compose`
- Weekly backup of PostgreSQL and uploaded media to NFS storage

## Restore from backup

Each backup archive contains:

- `postgres.sql`
- `media/`

To restore the system on the remote host, use the Ansible restore playbook:

```bash
ansible-playbook -i ansible/inventory.yml ansible/restore.yml -e "backup_file_name=<backup-file-name>"
```

Example:

```bash
ansible-playbook -i ansible/inventory.yml ansible/restore.yml -e "backup_file_name=20260605-021500.tar.gz"
```

What the restore playbook does:

1. Extracts the selected backup archive
2. Runs a PostgreSQL permission preflight check
3. Drops and recreates the target PostgreSQL database
4. Restores `postgres.sql`
5. Replaces the deployed `media/` directory with the archived one
6. Starts the Docker Compose stack again

Important:

- Run restore only when you intentionally want to replace the current database and uploaded media
- The current deployed database and media will be overwritten
- Use a backup file from the same environment unless you explicitly want cross-environment recovery
- The restore playbook now fails early if the configured PostgreSQL role cannot terminate connections, recreate the database, or operate on the existing target database

### Restore in local development without Ansible

If you are running the app locally with a Python virtual environment instead of Docker Compose, use the restore script below.

The script works on both Linux and macOS and reads database connection settings from `config/.env`:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

Expected local backup location:

```bash
volumes/backup/<backup-file-name>.tar.gz
```

Example:

```bash
./scripts/restore_local.sh 20260605-021500.tar.gz
```

You can also pass an explicit path:

```bash
./scripts/restore_local.sh ./volumes/backup/20260605-021500.tar.gz
```

What the script does:

1. Loads `config/.env`
2. Extracts the selected backup archive to a temporary directory
3. Terminates active PostgreSQL connections to the target database
4. Drops and recreates the local database
5. Restores `postgres.sql`
6. Replaces the local `media/` directory with the archived `media/`
7. Cleans up the temporary restore directory automatically

Requirements on Linux and macOS:

- `bash`
- `tar`
- `psql`
- `dropdb`
- `createdb`

Database permission note:

- The script does not strictly require the PostgreSQL `root` account.
- It does require a PostgreSQL user with enough privileges to:
  - connect to the `postgres` database
  - terminate active connections to the target database
  - drop the target database
  - recreate the target database
  - restore `postgres.sql` into the recreated database
- In practice, this usually means a superuser account such as `postgres`, or another database role with equivalent privileges.
- The script performs a preflight permission check before restore starts, so it should fail early with a clear message instead of stopping halfway through the restore process.

Useful options:

```bash
./scripts/restore_local.sh --yes 20260605-021500.tar.gz
./scripts/restore_local.sh --env-file ./config/.env 20260605-021500.tar.gz
```

Important:

- The script overwrites your current local database and `media/`
- The script assumes the backup archive contains both `postgres.sql` and `media/`
- If your Django dev server is already running, restart it after restore completes

## Uploaded Media

Uploaded files are stored under `media/`.

Examples:

- Room images:
  - `media/rooms/<room_name>/...`
- Usage meter images:
  - `media/usages/<subscription_id>/<YYYY-MM>/...`

## Internationalization

The application supports:

- English
- Vietnamese

## License

This project is licensed under the [MIT License](/Users/anhvu/external/navu-house/LICENSE:1).

## Notes

- The project is designed for operator-focused workflows rather than public tenant self-service.
- Billing values are stored as snapshots in subscriptions and usage records to preserve historical data.
- Media files should be persisted on the deployment host and included in backups.
