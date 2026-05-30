# Ansible deploy

## Install role

```bash
pip install ansible
ansible-galaxy install -r ansible/requiremens.yml -p ansible/.galaxy/roles
```

## Prepare local config

Copy the example files first:

```bash
cp ansible/group_vars/private.yml.example ansible/group_vars/private.yml
cp ansible/inventory.example ansible/inventory.yml
```

`private.yml` and `inventory.yml` stay ignored by Git, so use them for real server values and secrets.

## Fill inventory values

Edit:

- `ansible/inventory.yml`

Fields:

- `ansible_host`
  - The target server IP or hostname.
  - Example: `192.168.1.152`
- `ansible_user`
  - The SSH login user on the remote server.
  - Common values: `ubuntu`, `root`, `debian`
- `ansible_ssh_private_key_file`
  - Path to the SSH private key on your local machine.
  - Example: `~/.ssh/id_rsa`

## Fill deploy variables

Edit:

- `ansible/group_vars/private.yml`

Important values and how to fill them:

- `deploy_path`
  - Absolute path on the remote server where the app will be deployed.
  - Example: `/opt/navu-house`
- `deploy_archive_path`
  - Temporary archive path used during deployment on the local/remote flow.
  - Keep the default unless you have a reason to change it.
- `compose_project_name`
  - Docker Compose project name.
  - Used for container naming.
- `django_debug`
  - Use `false` for production.
- `django_allowed_hosts`
  - List every host/IP that will access the app.
  - Example:
    - server IP
    - local loopback
    - internal reverse-proxy hostname if used
- `postgres_db`
  - PostgreSQL database name used by Django.
  - Example: `navu_house`
- `postgres_user`
  - PostgreSQL username.
  - Example: `postgres`
- `postgres_password`
  - Strong PostgreSQL password.
  - Replace `change_me` before deploy.
- `postgres_port`
  - PostgreSQL container port exposed on the server.
  - Default: `5432`
- `redis_port`
  - Redis container port exposed on the server.
  - Default: `6379`
- `redis_url`
  - Redis connection string used by Django.
  - Usually keep `redis://redis:6379/1`
- `web_port`
  - Public HTTP port on the remote server.
  - Use `80` for normal HTTP, or another port if you run behind a reverse proxy.
- `gunicorn_workers`
  - Number of Gunicorn worker processes.
  - Start small, for example `2`
- `gunicorn_threads`
  - Number of threads per Gunicorn worker.
  - Start with `2` or `4`
- `backup_nfs_server`
  - IP or hostname of the NFS storage server.
- `backup_nfs_export`
  - Real exported NFS path from the storage server.
  - For Synology DSM this is often something like `/volume1/navu-house`
- `backup_nfs_mount_point`
  - Local mount path on the app server.
  - Example: `/mnt/navu-house`
- `backup_folder_name`
  - Folder created inside the mounted NFS path where backup archives are stored.
  - Example result: `/mnt/navu-house/backup/20260530-070344.tar.gz`
- `backup_schedule_weekday`
  - Weekly cron day.
  - `0` means Sunday
- `backup_schedule_hour`
  - Backup hour in 24-hour format.
- `backup_schedule_minute`
  - Backup minute.
- `backup_retention_days`
  - Number of days to keep old backup archives.
- `project_copy_excludes`
  - Local-only paths excluded from deployment archive.
  - Keep `media` here if the remote server stores uploads persistently.

## Run deploy

```bash
ansible-playbook -i ansible/inventory.yml ansible/deploy.yml
```

## What the playbook does

1. Installs Docker and Docker Compose plugin with `geerlingguy.docker`
2. Archives the local project
3. Excludes local-only directories such as `.venv` and `volumes`
4. Copies the archive to the remote host
5. Renders `docker-compose.override.yml` with deployment-specific environment variables
6. Runs `docker compose up -d --build`
7. Ensures the target PostgreSQL database exists, even if the remote Postgres volume was initialized earlier with another database name
8. Mounts the NFS backup share and schedules a weekly backup that stores PostgreSQL and uploaded media in one archive

## Notes

- Do not commit `ansible/group_vars/private.yml` or `ansible/inventory.yml`.
- Commit the example files so other environments can start from the same template.
- If you use Synology DSM for NFS, verify the exact export path with the DSM NFS settings before filling `backup_nfs_export`.
