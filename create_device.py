#!/usr/bin/env python3
"""
Create a device in NetBox via the REST API, building all of its prerequisites first.

A device cannot be created on its own. NetBox requires this dependency chain:
    manufacturer -> device type
    device role
    site
    => device (references device_type + role + site)

We also attach an interface + IP and set it as the device's PRIMARY IP, because the
Ansible dynamic-inventory plugin SILENTLY SKIPS devices that have no primary IP.

This script is IDEMPOTENT: running it repeatedly will not create duplicates.

Usage:
    export NETBOX_API=http://localhost:8000
    export NETBOX_TOKEN=<your token>
    python create_device.py
"""

import os
import sys
import requests

NETBOX_URL = os.environ.get("NETBOX_API", "http://localhost:8000").rstrip("/")
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN")

if not NETBOX_TOKEN:
    sys.exit("ERROR: set the NETBOX_TOKEN environment variable first.")

# --- Auth header -------------------------------------------------------------
# NetBox 4.5+ has two token formats:
#   v2 (new):     value looks like "nbt_<key>.<secret>"  -> Authorization: Bearer ...
#   v1 (legacy):  a single opaque string                 -> Authorization: Token ...
# This auto-detects which one you created.
if NETBOX_TOKEN.startswith("nbt_"):
    auth_header = f"Bearer {NETBOX_TOKEN}"      # v2
else:
    auth_header = f"Token {NETBOX_TOKEN}"       # v1 (legacy)

session = requests.Session()
session.headers.update(
    {
        "Authorization": auth_header,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
)


def get_or_create(endpoint, lookup, data):
    """Return an existing object matching `lookup` (query params), else create it with `data`."""
    url = f"{NETBOX_URL}/api/{endpoint}/"
    r = session.get(url, params=lookup)
    r.raise_for_status()
    results = r.json()["results"]
    if results:
        print(f"  exists : {endpoint} {lookup}")
        return results[0]
    r = session.post(url, json=data)
    if r.status_code >= 400:
        sys.exit(f"  ERROR creating {endpoint}: {r.status_code}\n{r.text}")
    print(f"  created: {endpoint} {lookup}")
    return r.json()


def main():
    print("1. Manufacturer")
    manufacturer = get_or_create(
        "dcim/manufacturers",
        {"slug": "acme"},
        {"name": "ACME", "slug": "acme"},
    )

    print("2. Device type")
    device_type = get_or_create(
        "dcim/device-types",
        {"slug": "acme-switch-1000"},
        {
            "manufacturer": manufacturer["id"],
            "model": "ACME Switch 1000",
            "slug": "acme-switch-1000",
        },
    )

    print("3. Device role")
    role = get_or_create(
        "dcim/device-roles",
        {"slug": "access-switch"},
        {"name": "Access Switch", "slug": "access-switch", "color": "2196f3"},
    )

    print("4. Site")
    site = get_or_create(
        "dcim/sites",
        {"slug": "denver-1"},
        {"name": "Denver 1", "slug": "denver-1", "status": "active"},
    )

    print("5. Device")
    # NOTE: in NetBox v4 the device's role field is "role".
    # In v3 it was "device_role". If you get a 400 here, check the field name in
    # the browsable API at http://localhost:8000/api/dcim/devices/
    device = get_or_create(
        "dcim/devices",
        {"name": "switch-denver-01"},
        {
            "name": "switch-denver-01",
            "device_type": device_type["id"],
            "role": role["id"],
            "site": site["id"],
            "status": "active",
        },
    )

    print("6. Interface")
    interface = get_or_create(
        "dcim/interfaces",
        {"device_id": device["id"], "name": "eth0"},
        {"device": device["id"], "name": "eth0", "type": "1000base-t"},
    )

    print("7. IP address")
    ip = get_or_create(
        "ipam/ip-addresses",
        {"address": "10.10.10.1/24"},
        {
            "address": "10.10.10.1/24",
            "status": "active",
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": interface["id"],
        },
    )

    print("8. Set the IP as the device's primary IPv4")
    r = session.patch(
        f"{NETBOX_URL}/api/dcim/devices/{device['id']}/",
        json={"primary_ip4": ip["id"]},
    )
    r.raise_for_status()
    print("  done")

    print(f"\nDevice ready: id={device['id']} name={device['name']} ip=10.10.10.1")
    print("It now has a primary IP, so it will appear in the Ansible dynamic inventory.")


if __name__ == "__main__":
    main()
