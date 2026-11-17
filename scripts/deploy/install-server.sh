#!/usr/bin/env bash
# Prepare a Debian or Ubuntu server for Frappe LMS. Runs ON the server.
# From the laptop, run it with:  scripts/deploy/deploy.sh install [--dry-run]
#
#   install-server.sh <domain> [<deploy-dir>]
#
# Safe to run more than once and safe on a server that hosts other apps:
#   - Docker is installed only if it is missing.
#   - Ports 8000 and 9000 must be free; nothing is stopped to free them.
#   - An nginx site is added for <domain> only if none exists for it. Other
#     sites are never changed. nginx is reloaded (not restarted), and only
#     after `nginx -t` passes.
#   - A TLS certificate is requested only when <domain> already resolves to
#     this server.
# With DRY_RUN=1, it checks everything and changes nothing.
set -Eeuo pipefail

# A non-interactive SSH session often lacks the sbin folders, where nginx lives.
export PATH="$PATH:/usr/local/sbin:/usr/sbin:/sbin"

DOMAIN="${1:?usage: install-server.sh <domain> [<deploy-dir>]}"
DEPLOY_DIR="${2:-/opt/lms}"
DRY="${DRY_RUN:-0}"
APP_PORT=8000
SOCKETIO_PORT=9000
SITE_FILE="/etc/nginx/sites-available/$DOMAIN"

step() { printf '\n==> %s\n' "$*"; }
ok()   { printf '    ok: %s\n' "$*"; }
todo() { printf '    %s %s\n' "$([[ $DRY == 1 ]] && echo '[dry-run] would' || echo 'doing:')" "$*"; }
warn() { printf '    warning: %s\n' "$*"; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }
run()  { [[ $DRY == 1 ]] || "$@"; }

[[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || die "not a valid domain: $DOMAIN"
sudo -n true 2>/dev/null || die "this user needs passwordless sudo for the installer"

# ---------------------------------------------------------------- system
step "Checking the system"
. /etc/os-release
[[ "$ID" == debian || "$ID" == ubuntu ]] || die "only Debian and Ubuntu are supported (found $ID)"
ok "$PRETTY_NAME, $(uname -m)"
avail_mb=$(free -m | awk '/Mem:/{print $7}')
if (( avail_mb < 2500 )); then
	warn "only ${avail_mb} MB RAM available; the LMS needs about 1.5 to 2.5 GB"
else
	ok "${avail_mb} MB RAM available"
fi

# ---------------------------------------------------------------- docker
step "Docker"
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
	ok "$(docker --version | cut -d, -f1), Compose $(docker compose version --short)"
else
	todo "install Docker Engine and the Compose plugin from Docker's apt repository"
	if [[ $DRY != 1 ]]; then
		sudo apt-get update -qq
		sudo apt-get install -y -qq ca-certificates curl
		sudo install -m 0755 -d /etc/apt/keyrings
		sudo curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
		sudo chmod a+r /etc/apt/keyrings/docker.asc
		echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$ID $VERSION_CODENAME stable" |
			sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
		sudo apt-get update -qq
		sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
	fi
fi
if docker ps >/dev/null 2>&1; then
	ok "$USER can run Docker"
else
	todo "add $USER to the docker group (log out and back in afterwards)"
	run sudo usermod -aG docker "$USER"
fi

# ---------------------------------------------------------------- ports
step "Ports"
for port in $APP_PORT $SOCKETIO_PORT; do
	if sudo ss -ltn "( sport = :$port )" | grep -q LISTEN; then
		die "port $port is already in use; the LMS needs it free"
	fi
	ok "port $port is free"
done

# ---------------------------------------------------------------- folder
step "Deploy folder"
if [[ -d "$DEPLOY_DIR" ]]; then
	ok "$DEPLOY_DIR exists"
else
	todo "create $DEPLOY_DIR owned by $USER"
	run sudo mkdir -p "$DEPLOY_DIR"
	run sudo chown "$USER:$USER" "$DEPLOY_DIR"
fi

# ---------------------------------------------------------------- nginx
step "nginx site for $DOMAIN"
if ! command -v nginx >/dev/null; then
	warn "nginx is not installed; skipping the reverse proxy (install nginx, then run this again)"
# Check nginx's live configuration, not the folder: sites-enabled holds symlinks,
# which a plain recursive grep does not follow, and any included file may serve the domain.
elif sudo test -e "$SITE_FILE" ||
	sudo nginx -T 2>/dev/null | grep -qE "^[[:space:]]*server_name[^;]*[[:space:]]${DOMAIN//./\\.}([[:space:]]|;)"; then
	ok "a site for $DOMAIN already exists; leaving it unchanged"
else
	todo "write $SITE_FILE (proxy to 127.0.0.1:$APP_PORT, socket.io to 127.0.0.1:$SOCKETIO_PORT), enable it, test and reload nginx"
	if [[ $DRY != 1 ]]; then
		sudo tee "$SITE_FILE" >/dev/null <<NGINX
# Frappe LMS. Written by scripts/deploy/install-server.sh.
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    client_max_body_size 50m;

    location /socket.io {
        proxy_pass http://127.0.0.1:$SOCKETIO_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
NGINX
		sudo ln -s "$SITE_FILE" "/etc/nginx/sites-enabled/$DOMAIN"
		if sudo nginx -t 2>/dev/null; then
			sudo systemctl reload nginx
			ok "nginx site enabled and reloaded"
		else
			sudo rm -f "/etc/nginx/sites-enabled/$DOMAIN" "$SITE_FILE"
			die "nginx -t failed with the new site; it was removed and nginx was not reloaded"
		fi
	fi
fi

# ---------------------------------------------------------------- tls
step "TLS certificate for $DOMAIN"
server_ips="$(hostname -I)"
# getent exits non-zero for a name that does not resolve; that is an answer, not an error.
domain_ip="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)"
if sudo test -d "/etc/letsencrypt/live/$DOMAIN"; then
	ok "a certificate for $DOMAIN already exists"
elif ! command -v certbot >/dev/null; then
	warn "certbot is not installed; skipping HTTPS"
elif [[ -z "$domain_ip" ]]; then
	warn "$DOMAIN does not resolve yet. Add a DNS A record pointing to $(echo $server_ips | awk '{print $1}'), then run this again."
elif [[ " $server_ips " != *" $domain_ip "* ]]; then
	warn "$DOMAIN resolves to $domain_ip, not this server ($server_ips). Fix the DNS record, then run this again."
else
	todo "request a Let's Encrypt certificate with certbot and redirect HTTP to HTTPS"
	run sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect
fi

step "Done"
echo "    Next, from the laptop: scripts/deploy/deploy.sh setup"
