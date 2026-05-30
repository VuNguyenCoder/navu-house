# Ansible deploy

## Install role

```bash
pip install ansible
ansible-galaxy install -r ansible/requiremens.yml -p ansible/.galaxy/roles
```

## Review deploy variables

Edit:

- `ansible/group_vars/private.yml`

Important values:

- `deploy_path`
- `django_allowed_hosts`
- `postgres_password`
- `web_port`
- `backup_nfs_server`
- `backup_nfs_export`

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
