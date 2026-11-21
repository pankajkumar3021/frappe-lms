#!/usr/bin/env bash
# Deploy Frappe LMS to a production server from this laptop over SSH.
#
#   scripts/deploy/deploy.sh install            prepare the server: Docker, folder, nginx site, HTTPS
#   scripts/deploy/deploy.sh setup              first-time setup of a new server
#   scripts/deploy/deploy.sh deploy [options]   build the image, back up, ship, restart
#   scripts/deploy/deploy.sh rollback           restart the previous image
#   scripts/deploy/deploy.sh backup             take a database + files backup now
#   scripts/deploy/deploy.sh status             show running containers and image tags
#   scripts/deploy/deploy.sh mcp                set up the MCP agents for Claude Code on the server
#
# Options for deploy:
#   --ref <git-ref>   git ref to build (default: value in deploy.env, else main)
#   --migrate         run bench migrate after the backup (schema changes)
#   --dry-run         print every step without changing anything
#
# The database and Redis containers are never recreated by a deploy. A backup runs
# before every deploy and the deploy stops if the backup fails.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG="$SCRIPT_DIR/deploy.env"
COMPOSE_FILE="$REPO_DIR/docker/prod/compose.yml"
# The image's build files, as repo paths; their content at the built commit is
# part of the image tag.
IMAGE_FILES=(docker/prod/Containerfile docker/prod/nginx.conf docker/prod/entrypoint.sh)
BUILD_SHA=""
PLATFORM_DEFAULT="linux/amd64"

DRY_RUN=0
MIGRATE=0
REF_OVERRIDE=""
BUILD_CTX=""

cleanup() { [[ -n "$BUILD_CTX" ]] && rm -rf "$BUILD_CTX"; return 0; }
trap cleanup EXIT

log()  { printf '\n==> %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

# run <description> <command...>: prints in dry-run mode, otherwise runs.
run() {
	local desc="$1"; shift
	if [[ $DRY_RUN -eq 1 ]]; then
		printf '    [dry-run] %s\n' "$desc"
		printf '              %s\n' "$*"
		return 0
	fi
	info "$desc"
	"$@"
}

load_config() {
	[[ -f "$CONFIG" ]] || die "missing $CONFIG. Run: scripts/deploy/deploy.sh setup (or copy deploy.env.example)"
	# shellcheck disable=SC1090
	source "$CONFIG"
	: "${DEPLOY_HOST:?set DEPLOY_HOST in deploy.env}"
	: "${DEPLOY_DIR:=/opt/lms}"
	: "${SITE_NAME:?set SITE_NAME in deploy.env}"
	: "${REF:=main}"
	: "${IMAGE_REPO:=lms-prod}"
	: "${PLATFORM:=$PLATFORM_DEFAULT}"
	# server: the server fetches the commit from GitHub and builds it (no image
	# upload). laptop: build here and copy the image over SSH.
	: "${BUILD_ON:=server}"
	[[ $BUILD_ON == server || $BUILD_ON == laptop ]] || die "BUILD_ON must be server or laptop"
	if [[ -z "${REPO_URL:-}" ]]; then
		REPO_URL="$(git -C "$REPO_DIR" remote get-url origin)"
		# The server clones anonymously, so use HTTPS for a GitHub SSH remote.
		[[ $REPO_URL == git@github.com:* ]] && REPO_URL="https://github.com/${REPO_URL#git@github.com:}"
	fi
}

# All SSH calls share one connection (ControlMaster), so a run makes one
# handshake instead of dozens. sshd drops new connections when too many arrive
# at once, and that broke a setup run part-way.
SSH_OPTS=(
	-o BatchMode=yes
	-o ConnectTimeout=15
	-o ServerAliveInterval=30
	-o ControlMaster=auto
	-o "ControlPath=$HOME/.ssh/lms-deploy-%C"
	-o ControlPersist=120
)

# Run a command on the server. -n keeps ssh off this script's stdin, so a remote
# call never swallows input meant for a later prompt (the setup password).
# Exit 255 means ssh itself failed to connect, so that is retried; any other
# exit code is the remote command's own result and is returned as is.
remote() {
	local attempt rc
	for attempt in 1 2 3; do
		rc=0
		ssh -n "${SSH_OPTS[@]}" "$DEPLOY_HOST" "$@" || rc=$?
		[[ $rc -ne 255 ]] && return $rc
		printf '    ssh connection failed (attempt %s of 3); retrying\n' "$attempt" >&2
		sleep $((attempt * 5))
	done
	return $rc
}

# The same, for the few calls that send data to the server on stdin. Not
# retried: the input is consumed by the first attempt.
remote_stdin() { ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" "$@"; }

# Compose against the server's project and .env. Prints a shell-quoted command
# line for ssh; every argument is quoted on its own.
rcompose() {
	local base
	printf -v base 'docker compose --project-directory %q -f %q --env-file %q' \
		"$DEPLOY_DIR" "$DEPLOY_DIR/compose.yml" "$DEPLOY_DIR/.env"
	printf '%s' "$base"
	local arg
	for arg in "$@"; do printf ' %q' "$arg"; done
}

check_local_tools() {
	command -v docker >/dev/null || die "docker is not installed on this laptop"
	command -v ssh >/dev/null || die "ssh is not installed on this laptop"
	command -v git >/dev/null || die "git is not installed on this laptop"
}

check_server() {
	log "Checking the server"
	if [[ $DRY_RUN -eq 1 ]]; then
		info "[dry-run] would check Docker and Compose on $DEPLOY_HOST"
		return 0
	fi
	remote "command -v docker >/dev/null && docker compose version >/dev/null" \
		|| die "Docker and the Compose plugin must be installed on $DEPLOY_HOST"
	info "Docker and Compose are available on $DEPLOY_HOST"
}

# ---------------------------------------------------------------- build

# Work out which commit to build and its image tag. The tag is the commit plus a
# hash of the image files (Containerfile, nginx.conf, entrypoint.sh) at that
# commit, so a change to either gives a new tag.
resolve_build() {
	local ref="$1" upstream f
	git -C "$REPO_DIR" fetch -q origin || die "could not fetch from origin"
	# Refuse to build a local branch that differs from GitHub, so a stale branch
	# is never deployed by accident.
	if upstream="$(git -C "$REPO_DIR" rev-parse -q --verify "origin/$ref^{commit}")"; then
		[[ "$(git -C "$REPO_DIR" rev-parse "$ref^{commit}")" == "$upstream" ]] ||
			die "local '$ref' differs from origin/$ref. Update it first: git fetch origin && git branch -f $ref origin/$ref"
	fi
	BUILD_SHA="$(git -C "$REPO_DIR" rev-parse "$ref^{commit}")" || die "git ref '$ref' does not exist"
	git -C "$REPO_DIR" merge-base --is-ancestor "$BUILD_SHA" "origin/$ref" 2>/dev/null ||
		git -C "$REPO_DIR" branch -r --contains "$BUILD_SHA" | grep -q . ||
		die "$ref ($BUILD_SHA) is not on GitHub; push it first"
	# The image is built from the commit, never the working tree.
	if [[ -n "$(git -C "$REPO_DIR" status --porcelain -- lms frontend docker 2>/dev/null)" ]]; then
		printf 'warning: uncommitted changes under lms/, frontend/ or docker/ are NOT in the image; only %s is built\n' "$ref" >&2
	fi
	BUILT_TAG="$IMAGE_REPO:${BUILD_SHA:0:12}-$(
		for f in "${IMAGE_FILES[@]}"; do git -C "$REPO_DIR" show "$BUILD_SHA:$f" 2>/dev/null; done |
			sha256sum | cut -c1-8
	)"
}

build_image() {
	resolve_build "$1"
	if [[ $BUILD_ON == server ]]; then
		build_on_server
	else
		build_on_laptop
	fi
}

# The server fetches the commit from GitHub and builds it there, so no image
# crosses the network. Its build cache makes a code-only change quick.
build_on_server() {
	if [[ $DRY_RUN -eq 1 ]]; then
		printf '    [dry-run] on %s: fetch %s from %s and build %s\n' "$DEPLOY_HOST" "${BUILD_SHA:0:12}" "$REPO_URL" "$BUILT_TAG"
		return 0
	fi
	info "Build $BUILT_TAG on $DEPLOY_HOST from $REPO_URL at ${BUILD_SHA:0:12}"
	remote_stdin "bash -s -- $(printf '%q ' "$REPO_URL" "$BUILD_SHA" "$BUILT_TAG" "$DEPLOY_DIR" "$PLATFORM")" <<'REMOTE'
set -Eeuo pipefail
repo_url="$1" sha="$2" tag="$3" dir="$4" platform="$5"
if docker image inspect "$tag" >/dev/null 2>&1; then
	echo "    the server already has $tag; not building it again"
	exit 0
fi
src="$dir/src/repo"
if [ ! -d "$src/.git" ]; then
	mkdir -p "$dir/src"
	git clone -q --filter=blob:none --no-checkout "$repo_url" "$src"
fi
git -C "$src" remote set-url origin "$repo_url"
git -C "$src" fetch -q origin "$sha"
ctx="$(mktemp -d)"
trap 'rm -rf "$ctx"' EXIT
mkdir "$ctx/lms-src"
git -C "$src" archive "$sha" | tar -x -C "$ctx/lms-src"
cp "$ctx/lms-src/docker/prod/Containerfile" "$ctx/lms-src/docker/prod/nginx.conf" \
	"$ctx/lms-src/docker/prod/entrypoint.sh" "$ctx/"
docker build --network host --platform "$platform" --build-arg "LMS_VERSION=${sha:0:12}" \
	-t "$tag" -f "$ctx/Containerfile" "$ctx"
REMOTE
}

# Build here and copy the image to the server afterwards (ship_image).
build_on_laptop() {
	local ctx
	ctx="$(mktemp -d)"
	BUILD_CTX="$ctx"
	mkdir -p "$ctx/lms-src"
	git -C "$REPO_DIR" archive --format=tar "$BUILD_SHA" | tar -x -C "$ctx/lms-src"
	cp "$ctx/lms-src/docker/prod/Containerfile" "$ctx/lms-src/docker/prod/nginx.conf" \
		"$ctx/lms-src/docker/prod/entrypoint.sh" "$ctx/"
	# Host networking avoids the flaky DNS of Docker's build network on some laptops.
	# UV_DEFAULT_INDEX lets the build use a faster PyPI mirror.
	local build_args=(--build-arg "LMS_VERSION=${BUILD_SHA:0:12}")
	[[ -n "${UV_DEFAULT_INDEX:-}" ]] && build_args+=(--build-arg "UV_DEFAULT_INDEX=$UV_DEFAULT_INDEX")
	run "Build image $BUILT_TAG from ${BUILD_SHA:0:12} on this laptop for $PLATFORM" \
		docker build --network "${BUILD_NETWORK:-host}" --platform "$PLATFORM" -f "$ctx/Containerfile" \
			"${build_args[@]}" -t "$BUILT_TAG" "$ctx"
}

# ---------------------------------------------------------------- ship

ship_image() {
	local tag="$1"
	if [[ $DRY_RUN -eq 0 ]] && remote "docker image inspect $(printf '%q' "$tag") >/dev/null 2>&1"; then
		info "$DEPLOY_HOST already has $tag; nothing to copy"
		return 0
	fi
	if [[ $DRY_RUN -eq 1 ]]; then
		[[ $BUILD_ON == server ]] && return 0
		printf '    [dry-run] copy %s to %s over SSH (docker save | gzip | ssh docker load)\n' "$tag" "$DEPLOY_HOST"
		return 0
	fi
	info "Copy $tag to $DEPLOY_HOST over SSH (docker save | gzip | docker load)"
	docker save "$tag" | gzip | ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" 'gunzip | docker load'
}

# ---------------------------------------------------------------- server state

current_tag() {
	[[ $DRY_RUN -eq 1 ]] && return 0
	remote "cat '$DEPLOY_DIR/state/current' 2>/dev/null || true"
}

set_remote_image() {
	local tag="$1"
	run "Point LMS_IMAGE at $tag on the server" \
		remote "sed -i 's|^LMS_IMAGE=.*|LMS_IMAGE=$tag|' '$DEPLOY_DIR/.env'"
}

record_state() {
	local tag="$1"
	remote "mkdir -p '$DEPLOY_DIR/state' && { cat '$DEPLOY_DIR/state/current' 2>/dev/null > '$DEPLOY_DIR/state/previous' || true; } && echo '$tag' > '$DEPLOY_DIR/state/current'"
}

wait_healthy() {
	local tries=30
	if [[ $DRY_RUN -eq 1 ]]; then
		printf '    [dry-run] wait for http://127.0.0.1:8000/api/method/ping (Host: %s) on the server\n' "$SITE_NAME"
		return 0
	fi
	info "Waiting for the site to answer"
	for _ in $(seq "$tries"); do
		if remote "curl -fsS -o /dev/null -H $(printf '%q' "Host: $SITE_NAME") http://127.0.0.1:8000/api/method/ping"; then
			info "The site answers"
			return 0
		fi
		sleep 5
	done
	return 1
}

# ---------------------------------------------------------------- backup

backup() {
	log "Backing up $SITE_NAME (database and files)"
	run "bench backup --with-files for $SITE_NAME" \
		remote "$(rcompose exec -T app bench --site "$SITE_NAME" backup --with-files)"
	info "Backups stay in the sites volume. List them with: scripts/deploy/deploy.sh status"
}

# ---------------------------------------------------------------- commands

cmd_deploy() {
	load_config
	check_local_tools
	check_server
	local ref="${REF_OVERRIDE:-$REF}"

	log "Building $IMAGE_REPO from $ref (on the $BUILD_ON)"
	build_image "$ref"

	log "Backing up before the change"
	backup

	log "Shipping the image to $DEPLOY_HOST"
	ship_image "$BUILT_TAG"

	local previous
	previous="$(current_tag)"
	[[ -n "$previous" ]] && info "Currently running: $previous"

	log "Restarting the application containers"
	# The compose file can change with the image (new services, ports), so it ships
	# too. The previous one is kept for rollback.
	run "Copy the production compose file to the server (previous kept as compose.yml.previous)" \
		bash -c "ssh ${SSH_OPTS[*]} '$DEPLOY_HOST' 'cp -f $DEPLOY_DIR/compose.yml $DEPLOY_DIR/compose.yml.previous' && scp -q ${SSH_OPTS[*]} '$COMPOSE_FILE' '$DEPLOY_HOST:$DEPLOY_DIR/compose.yml'"
	set_remote_image "$BUILT_TAG"
	run "Recreate app, frontend, worker, scheduler and socketio (database and Redis untouched)" \
		remote "$(rcompose up -d --no-deps app frontend worker scheduler socketio)"

	# An app added to the image (in sites/apps.txt, which the entrypoint copies from
	# the image) is not on the site yet; migrate does not install apps, so do it here.
	log "Installing apps the image added to $SITE_NAME"
	run "bench install-app for each app in apps.txt not yet on the site" \
		remote "$(rcompose exec -T -e SITE="$SITE_NAME" app sh -c 'set -e
installed=$(bench --site "$SITE" execute frappe.get_installed_apps)
for app in $(cat sites/apps.txt); do
	case "$installed" in
		*"\"$app\""*) ;;
		*) echo "    installing $app"; bench --site "$SITE" install-app "$app" ;;
	esac
done')"

	if [[ $MIGRATE -eq 1 ]]; then
		log "Migrating $SITE_NAME (schema changes; backup already taken)"
		run "bench --site $SITE_NAME migrate" \
			remote "$(rcompose exec -T app bench --site "$SITE_NAME" migrate)"
	fi

	log "Checking the site"
	if wait_healthy; then
		clear_site_cache
		[[ $DRY_RUN -eq 1 ]] || record_state "$BUILT_TAG"
		prune_images
		log "Deployed $BUILT_TAG to $DEPLOY_HOST"
	else
		printf 'The site did not answer after the deploy. Rolling back.\n' >&2
		if [[ -n "$previous" ]]; then
			rollback_to "$previous"
		fi
		die "deploy failed; the previous image is running. Database was not restored."
	fi
}

# Keep only the running image and the previous one (for rollback); older images
# just take disk space. The build cache is kept, so later builds stay fast.
prune_images() {
	run "Remove $IMAGE_REPO images other than the current and previous ones" \
		remote "keep=\" \$(cat '$DEPLOY_DIR/state/current' 2>/dev/null) \$(cat '$DEPLOY_DIR/state/previous' 2>/dev/null) \"; for img in \$(docker images $IMAGE_REPO --format '{{.Repository}}:{{.Tag}}'); do case \"\$keep\" in *\" \$img \"*|*\" \$img\") ;; *) docker image rm \"\$img\" >/dev/null 2>&1 && echo \"    removed \$img\" || true ;; esac; done"
}

# Frappe keeps routes, redirects and hooks in Redis, which a new image does not
# reset: without this, an old redirect can outlive the code that defined it.
clear_site_cache() {
	run "Clear the site cache" \
		remote "$(rcompose exec -T app sh -c "bench --site $SITE_NAME clear-cache && bench --site $SITE_NAME clear-website-cache")"
}

rollback_to() {
	local tag="$1"
	# Put back the compose file that went with the previous image, if the deploy
	# saved one, so an older image is not started with services it cannot run.
	run "Restore the previous compose file, if there is one" \
		remote "if [ -f '$DEPLOY_DIR/compose.yml.previous' ]; then cp -f '$DEPLOY_DIR/compose.yml' '$DEPLOY_DIR/compose.yml.failed' && mv -f '$DEPLOY_DIR/compose.yml.previous' '$DEPLOY_DIR/compose.yml'; fi"
	set_remote_image "$tag"
	# No service list: services missing from the restored file are removed as
	# orphans. The database and Redis are unchanged, so Compose leaves them running.
	run "Restart app containers on $tag" \
		remote "$(rcompose up -d --remove-orphans)"
	clear_site_cache
	[[ $DRY_RUN -eq 1 ]] || record_state "$tag"
}

cmd_rollback() {
	load_config
	check_local_tools
	check_server
	local previous
	previous="$(remote "cat '$DEPLOY_DIR/state/previous' 2>/dev/null || true")"
	[[ -n "$previous" ]] || die "no previous image is recorded on $DEPLOY_HOST"
	log "Rolling back to $previous (the database is not restored)"
	rollback_to "$previous"
	wait_healthy || die "the site did not answer after the rollback; check: scripts/deploy/deploy.sh status"
	log "Rolled back to $previous"
}

cmd_backup() {
	load_config
	check_local_tools
	check_server
	backup
}

cmd_status() {
	load_config
	check_local_tools
	check_server
	log "Current image"
	remote "cat '$DEPLOY_DIR/state/current' 2>/dev/null || echo '(none recorded)'"
	log "Containers"
	remote "$(rcompose ps)"
	log "Backups for $SITE_NAME"
	remote "$(rcompose exec -T app sh -c "ls -lt sites/$SITE_NAME/private/backups | head -6")" || true
}

cmd_setup() {
	check_local_tools
	log "First-time setup"
	if [[ ! -f "$CONFIG" ]]; then
		die "create $CONFIG first (copy scripts/deploy/deploy.env.example and fill it in)"
	fi
	load_config
	check_server

	log "Preparing $DEPLOY_DIR on the server"
	run "Create $DEPLOY_DIR, state and backups directories" \
		remote "mkdir -p '$DEPLOY_DIR/state' '$DEPLOY_DIR/backups'"

	local env_exists=0
	if [[ $DRY_RUN -eq 0 ]] && remote "[ -f '$DEPLOY_DIR/.env' ]"; then env_exists=1; fi

	if [[ $env_exists -eq 0 ]]; then
		local db_pw admin_pw
		if [[ $DRY_RUN -eq 1 ]]; then
			db_pw="<generated at setup>"
		else
			# head closes the pipe early, so tr may get SIGPIPE; that is expected here.
			db_pw="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32 || true)"
		fi
		if [[ $DRY_RUN -eq 1 ]]; then
			admin_pw="(dry run: not prompted)"
		else
			printf 'Admin password for the new site (not stored anywhere in the repo): '
			read -r -s admin_pw; echo
			[[ ${#admin_pw} -ge 8 ]] || die "admin password must be at least 8 characters"
		fi
		ADMIN_PW="$admin_pw"
		run "Write $DEPLOY_DIR/.env on the server (secrets stay on the server, mode 600)" \
			bash -c "printf 'SITE_NAME=%s\nDB_ROOT_PASSWORD=%s\nLMS_IMAGE=\n' '$SITE_NAME' '$db_pw' | ssh -o BatchMode=yes '$DEPLOY_HOST' 'cat > $DEPLOY_DIR/.env && chmod 600 $DEPLOY_DIR/.env'"
	else
		info "Found an existing .env on the server; keeping its secrets"
	fi
	run "Copy the production compose file to the server" \
		scp -q "${SSH_OPTS[@]}" "$COMPOSE_FILE" "$DEPLOY_HOST:$DEPLOY_DIR/compose.yml"

	build_image "$REF"
	ship_image "$BUILT_TAG"
	set_remote_image "$BUILT_TAG"

	log "Starting the database and Redis"
	run "Start mariadb and redis" remote "$(rcompose up -d mariadb redis)"
	run "Wait for mariadb" remote "for i in \$(seq 60); do $(rcompose exec -T mariadb healthcheck.sh --connect --innodb_initialized) >/dev/null 2>&1 && exit 0; sleep 2; done; exit 1"

	log "Configuring the bench to use the containers"
	for cfg in "-g db_host mariadb" "-g redis_cache redis://redis:6379" \
		"-g redis_queue redis://redis:6379" "-g redis_socketio redis://redis:6379"; do
		run "bench set-config $cfg" remote "$(rcompose run --rm --no-deps -T app bench set-config $cfg)"
	done

	log "Creating the site $SITE_NAME (first time only)"
	if [[ $DRY_RUN -eq 1 ]]; then
		printf '    [dry-run] bench new-site %s, install payments and lms\n' "$SITE_NAME"
	else
		if remote "$(rcompose exec -T app test -d "sites/$SITE_NAME")" >/dev/null 2>&1; then
			die "site $SITE_NAME already exists on the server; setup will not recreate it"
		fi
		# Asked here, not only when .env is first written: a run that stopped after
		# writing .env must still be able to create the site on a later run.
		if [[ -z "${ADMIN_PW:-}" ]]; then
			printf 'Admin password for the new site (not stored anywhere in the repo): '
			read -r -s ADMIN_PW
			echo
			[[ ${#ADMIN_PW} -ge 8 ]] || die "admin password must be at least 8 characters"
		fi
		printf '%s\n' "$ADMIN_PW" | remote_stdin "read -r ADMIN_PASSWORD && export ADMIN_PASSWORD && $(rcompose run --rm --no-deps -T -e ADMIN_PASSWORD app sh -c "bench new-site $SITE_NAME --mariadb-root-password \"\$DB_ROOT_PASSWORD\" --admin-password \"\$ADMIN_PASSWORD\" --no-mariadb-socket && bench --site $SITE_NAME install-app payments && bench --site $SITE_NAME install-app lms && bench --site $SITE_NAME enable-scheduler && bench use $SITE_NAME")"
	fi

	log "Starting the application"
	run "Start app, frontend, worker, scheduler and socketio" remote "$(rcompose up -d app frontend worker scheduler socketio)"
	wait_healthy || die "the site did not answer; check: scripts/deploy/deploy.sh status"
	[[ $DRY_RUN -eq 1 ]] || record_state "$BUILT_TAG"
	log "Setup finished. Put a reverse proxy in front of 127.0.0.1:8000 for https://$SITE_NAME"
}

# ---------------------------------------------------------------- install

# Runs scripts/deploy/install-server.sh on the server. A dry run still connects,
# because the installer's checks read the server, but it changes nothing.
cmd_install() {
	load_config
	check_local_tools
	log "Preparing $DEPLOY_HOST for $SITE_NAME"
	local dry=0
	[[ $DRY_RUN -eq 1 ]] && dry=1
	ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" \
		"DRY_RUN=$dry bash -s -- $(printf '%q' "$SITE_NAME") $(printf '%q' "$DEPLOY_DIR")" \
		< "$SCRIPT_DIR/install-server.sh"
}

# ---------------------------------------------------------------- mcp

# The script that runs on the server. API secrets are written to token files there
# and never printed or sent back to the laptop.
mcp_remote_script() {
	local dir site
	printf -v dir '%q' "$DEPLOY_DIR"
	printf -v site '%q' "$SITE_NAME"
	cat <<EOF
set -euo pipefail
DIR=$dir
SITE=$site
cd "\$DIR"
mkdir -p mcp && chmod 700 mcp
# Requests from the server's own shell reach the app container from this address.
GW=\$(docker network inspect lms-prod_default -f '{{(index .IPAM.Config 0).Gateway}}')
[ -n "\$GW" ] || { echo "error: could not find the gateway of the lms-prod_default network" >&2; exit 1; }
OUT=\$(mktemp)
trap 'rm -f "\$OUT"' EXIT
docker compose --project-directory "\$DIR" -f "\$DIR/compose.yml" --env-file "\$DIR/.env" \\
	exec -T -e AGENT_IP="\$GW" -e AGENT_DOMAIN="\$SITE" app bench --site "\$SITE" console > "\$OUT" 2>&1 <<'PY'
$(mcp_python)
PY
umask 077
grep -oE 'TOKEN (course-agent|enrolment-agent) [A-Za-z0-9]+:[A-Za-z0-9]+' "\$OUT" | while read -r _ name tok; do
	printf '%s\n' "\$tok" > "mcp/\$name.token"
done
grep -oE 'STATUS .*' "\$OUT" || { echo "error: the MCP setup did not report back" >&2; grep -v 'TOKEN' "\$OUT" | tail -20 >&2; exit 1; }
EOF
}

# Python for bench console. IPython needs the blank line after the for block.
mcp_python() {
	cat <<'PY'
import os, frappe
from frappe.core.doctype.user.user import generate_keys
frappe.db.set_single_value("System Settings", "enable_mcp", 1)
domain = os.environ["AGENT_DOMAIN"]; ip = os.environ["AGENT_IP"]
agents = [("course-agent", "Course", "Creator", ["Course Creator", "Desk User"]), ("enrolment-agent", "Enrolment", "Manager", ["Moderator", "Desk User"])]
for slug, first, last, roles in agents:
    email = slug + "@" + domain
    if not frappe.db.exists("User", email):
        frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "last_name": last, "send_welcome_email": 0}).insert(ignore_permissions=True)
    user = frappe.get_doc("User", email)
    user.add_roles(*roles)
    user.restrict_ip = ip
    user.save(ignore_permissions=True)
    secret = generate_keys(email)["api_secret"]
    frappe.db.commit()
    print("TOKEN", slug, frappe.db.get_value("User", email, "api_key") + ":" + secret)
    print("STATUS", email, "| roles:", ", ".join(r for r in roles if r in frappe.get_roles(email)), "| restricted to:", ip)

PY
}

cmd_mcp() {
	load_config
	check_local_tools
	check_server
	log "Setting up the MCP agents on $SITE_NAME"
	info "course-agent@$SITE_NAME     Course Creator, Desk User"
	info "enrolment-agent@$SITE_NAME  Moderator, Desk User"
	info "Running this again issues new keys; the previous keys stop working."
	if [[ $DRY_RUN -eq 1 ]]; then
		printf '    [dry-run] on %s: enable MCP, create or update both agents, restrict them to the Docker gateway IP,\n' "$DEPLOY_HOST"
		printf '              write new tokens to %s/mcp/<agent>.token (mode 600)\n' "$DEPLOY_DIR"
	else
		mcp_remote_script | remote_stdin "bash -s"
	fi

	log "On the server, register the agents with Claude Code"
	local agent server
	for agent in course-agent enrolment-agent; do
		[[ $agent == course-agent ]] && server="lms-courses" || server="lms-enrolment"
		printf '    claude mcp add --scope user --transport http %s http://127.0.0.1:8000/api/v2/mcp --header "Authorization: token $(cat %s/mcp/%s.token)" --header "Host: %s"\n' \
			"$server" "$DEPLOY_DIR" "$agent" "$SITE_NAME"
	done
	info "The token files belong to the SSH user. Copy them to the account that runs Claude Code if that is a different user."
	info "Check with: claude mcp list   (both should show Connected)"
}

# ---------------------------------------------------------------- args

COMMAND="${1:-}"
shift || true
while [[ $# -gt 0 ]]; do
	case "$1" in
		--ref) REF_OVERRIDE="${2:?--ref needs a value}"; shift ;;
		--migrate) MIGRATE=1 ;;
		--dry-run) DRY_RUN=1 ;;
		-h|--help) sed -n '2,18p' "$0"; exit 0 ;;
		*) die "unknown option: $1" ;;
	esac
	shift
done

case "$COMMAND" in
	install) cmd_install ;;
	setup) cmd_setup ;;
	deploy) cmd_deploy ;;
	rollback) cmd_rollback ;;
	backup) cmd_backup ;;
	status) cmd_status ;;
	mcp) cmd_mcp ;;
	*) sed -n '2,18p' "$0"; exit 2 ;;
esac
