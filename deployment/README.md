# Shauryas Cricket Deployment

Reference files for the DigitalOcean Droplet deployment.

Live layout used on the Droplet:

```text
/opt/shauryascricket/app
/opt/shauryascricket/venv
/etc/systemd/system/shauryascricket-api.service
/etc/nginx/sites-available/shauryascricket.conf
Postgres DB: shauryascricket
Backend port: 127.0.0.1:8001
```

The existing trading app uses `127.0.0.1:8000`; keep Shauryas Cricket on
`8001` to avoid conflicts.

## Deploy Steps

1. Create/update the app directory:

```bash
mkdir -p /opt/shauryascricket/app
tar -xzf /tmp/shauryascricket-src.tar.gz -C /opt/shauryascricket/app
```

2. Create Postgres role/database and restore a dump:

```bash
sudo -u postgres psql -c "create role shauryas with login password 'CHANGE_ME';"
sudo -u postgres createdb -O shauryas shauryascricket
sudo -u postgres pg_restore --clean --if-exists --no-owner --role=shauryas -d shauryascricket /tmp/shauryascricket.dump
```

3. Install backend dependencies:

```bash
python3 -m venv /opt/shauryascricket/venv
/opt/shauryascricket/venv/bin/pip install -r /opt/shauryascricket/app/backend/requirements.txt
cp deployment/backend.env.example /opt/shauryascricket/app/backend/.env
```

4. Build frontend:

```bash
cd /opt/shauryascricket/app/frontend
npm ci
VITE_API_BASE_URL=https://shauryascricket.com npm run build
```

5. Install service and Nginx config:

```bash
cp deployment/shauryascricket-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now shauryascricket-api

cp deployment/nginx-shauryascricket.conf /etc/nginx/sites-available/shauryascricket.conf
ln -sfn /etc/nginx/sites-available/shauryascricket.conf /etc/nginx/sites-enabled/shauryascricket.conf
nginx -t
systemctl reload nginx
```

## Cloudflare

DNS records:

```text
A  @    143.198.120.202
A  www  143.198.120.202
```

Current simple setup:

```text
Proxy status: Proxied
SSL/TLS mode: Full
```

For `Full strict`, install a valid origin certificate and update the Nginx SSL
certificate paths.
