#!/usr/bin/env bash
# Move files between this laptop and the production server.
#
# Uses SFTP and rsync over the same SSH login as deploy.sh (DEPLOY_HOST in
# deploy.env). Plain FTP is not used: it sends the password unencrypted, and
# the server runs no FTP service.
#
#   scripts/deploy/transfer.sh put <local-path>... [--to <remote-dir>]
#       Upload files or folders. Default destination: $DEPLOY_DIR/uploads
#   scripts/deploy/transfer.sh get <remote-path> [<local-dir>]
#       Download a file or folder. Default destination: ./downloads
#   scripts/deploy/transfer.sh backups [<local-dir>]
#       Copy the site's database and file backups to this laptop.
#       Default destination: ./backups/<site>
#   scripts/deploy/transfer.sh sftp
#       Open an interactive SFTP session in $DEPLOY_DIR.
#
# Add --dry-run to put, get or backups to see what would be copied.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$SCRIPT_DIR/deploy.env"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,20p' "$0"; exit "${1:-0}"; }

[[ -f "$CONFIG" ]] || die "missing $CONFIG (copy deploy.env.example and fill it in)"
# shellcheck disable=SC1090
source "$CONFIG"
: "${DEPLOY_HOST:?set DEPLOY_HOST in deploy.env}"
: "${DEPLOY_DIR:=/opt/lms}"
: "${SITE_NAME:=}"

command -v rsync >/dev/null || die "rsync is not installed on this laptop"

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15)
RSYNC=(rsync -a --partial --human-readable --info=progress2 -e "ssh ${SSH_OPTS[*]}")

cmd="${1:-}"
shift || true
DRY=()
args=()
for a in "$@"; do
	[[ "$a" == "--dry-run" ]] && DRY=(--dry-run --itemize-changes) || args+=("$a")
done
set -- "${args[@]+"${args[@]}"}"

case "$cmd" in
	put)
		dest="$DEPLOY_DIR/uploads"
		sources=()
		while [[ $# -gt 0 ]]; do
			if [[ "$1" == "--to" ]]; then dest="${2:?--to needs a remote folder}"; shift 2; continue; fi
			[[ -e "$1" ]] || die "no such local file or folder: $1"
			sources+=("$1"); shift
		done
		[[ ${#sources[@]} -gt 0 ]] || die "put needs at least one local file or folder"
		[[ ${#DRY[@]} -gt 0 ]] || ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" "mkdir -p '$dest'"
		"${RSYNC[@]}" "${DRY[@]}" "${sources[@]}" "$DEPLOY_HOST:$dest/"
		echo "Uploaded to $DEPLOY_HOST:$dest/"
		;;
	get)
		remote="${1:?get needs a remote path}"
		dest="${2:-./downloads}"
		mkdir -p "$dest"
		# --copy-links: download what a symlink points to, not a link that breaks on the laptop.
		"${RSYNC[@]}" "${DRY[@]}" --copy-links "$DEPLOY_HOST:$remote" "$dest/"
		echo "Downloaded to $dest/"
		;;
	backups)
		[[ -n "$SITE_NAME" ]] || die "set SITE_NAME in deploy.env"
		dest="${1:-./backups/$SITE_NAME}"
		mkdir -p "$dest"
		# Backups live in the sites volume; read them through the app container.
		vol="$(ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" "docker volume inspect lms-prod_sites -f '{{.Mountpoint}}'")"
		[[ -n "$vol" ]] || die "the lms-prod_sites volume was not found on the server"
		"${RSYNC[@]}" "${DRY[@]}" --rsync-path="sudo rsync" \
			"$DEPLOY_HOST:$vol/$SITE_NAME/private/backups/" "$dest/"
		echo "Backups copied to $dest/"
		;;
	sftp)
		exec sftp -o ConnectTimeout=15 "$DEPLOY_HOST:$DEPLOY_DIR"
		;;
	-h|--help|"") usage 0 ;;
	*) die "unknown command: $cmd (try --help)" ;;
esac
