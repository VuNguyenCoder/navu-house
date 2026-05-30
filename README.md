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
