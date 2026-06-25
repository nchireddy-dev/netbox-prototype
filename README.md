# NetBox + Ansible Prototype — Runbook

Two directories, side by side:

```
~/work/
├── netbox-docker/      # cloned, run as-is — gives you a running NetBox
└── netbox-prototype/   # THIS folder — your script + playbook
```

---

## Prerequisites (control machine)
- Docker Desktop running
- Python 3.12+
- `pip install -r requirements.txt`   (requests, pynetbox, ansible)
- `ansible-galaxy collection install netbox.netbox`
  (The nb_inventory plugin needs the `pynetbox` library installed too — it's in requirements.txt.)

---

## Phase 1 — Run NetBox (in netbox-docker/)
```bash
git clone -b release https://github.com/netbox-community/netbox-docker.git
cd netbox-docker
cp docker-compose.override.yml.example docker-compose.override.yml
docker compose pull
docker compose up        # leave this running; first boot takes a few minutes
```
Open http://localhost:8000  (you should see the NetBox homepage).

In a second terminal, create your admin login:
```bash
cd netbox-docker
docker compose exec netbox /opt/netbox/netbox/manage.py createsuperuser
```

Create an API token in the UI:
- Log in at http://localhost:8000 with the superuser you just made.
- Top-right user menu → API Tokens → Add a token.
- EASIEST: if a "version" selector is shown, choose **v1 (legacy)** — it works everywhere
  with no extra config. Copy the token value immediately (shown once).
- (Optional, v2 token: requires API_TOKEN_PEPPER_1 to be set in the netbox container's
  environment. Skip unless you want the talking point.)

---

## Phase 2 — Create a device via the API (in netbox-prototype/)
```bash
cd ../netbox-prototype
export NETBOX_API=http://localhost:8000
export NETBOX_TOKEN=<paste your token>
python create_device.py
```
Re-run it — it's idempotent, so it prints "exists" instead of creating duplicates.
Verify in the UI: Devices → you should see `switch-denver-01` with primary IP 10.10.10.1.

---

## Phase 3 — Use NetBox as a dynamic inventory (in netbox-prototype/)
Same two env vars must be set (NETBOX_API, NETBOX_TOKEN).
```bash
# See the inventory Ansible pulls from NetBox:
ansible-inventory -i netbox_inv.yml --graph
ansible-inventory -i netbox_inv.yml --list

# Run the playbook that prints each device:
ansible-playbook -i netbox_inv.yml playbook.yml
```
You should see groups like `device_roles_access_switch` and `sites_denver_1`
containing `switch-denver-01`.

GOTCHA: a device with no primary IP is silently skipped by the inventory.
create_device.py assigns one for exactly this reason.

---

## Phase 4 (optional) — Tie into AWX
1. `git init` this folder, push it to a GitHub repo.
2. Spin up AWX (use your AMP `just start ...` commands).
3. In AWX: create a Credential for NetBox (exposes NETBOX_API + NETBOX_TOKEN env vars),
   add this repo as a Project, build an Execution Environment image containing the
   `netbox.netbox` collection, add an Inventory with a NetBox source, then a Job Template
   tying Project + playbook + Inventory + Credential + EE together, and run it.
If you run out of time, just be able to describe this flow — that's most of the value.
