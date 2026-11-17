#!/bin/sh
# Container entrypoint: point sites/assets at this image's built assets, then run
# the command.
#
# sites/ is a volume, so a real sites/assets folder in it would keep the CSS and
# JS of whichever image first created the volume, and every later deploy would
# serve stale files. The image keeps its assets in /home/frappe/frappe-bench/
# built-assets, and sites/assets is a relative symlink to it. Every container
# runs the same image, so they all agree on where that link points.
set -e

sites=/home/frappe/frappe-bench/sites
target=../built-assets

if [ "$(readlink "$sites/assets" 2>/dev/null)" != "$target" ]; then
	# A real folder left by an older image: move it aside first (another
	# container starting at the same moment may already have done so).
	if [ -d "$sites/assets" ] && [ ! -L "$sites/assets" ]; then
		mv "$sites/assets" "$sites/.assets-old-$$" 2>/dev/null || true
	fi
	# Create the link under a temporary name, then rename it into place, so the
	# swap is atomic.
	ln -sfn "$target" "$sites/.assets-link-$$"
	mv -Tf "$sites/.assets-link-$$" "$sites/assets" 2>/dev/null || rm -f "$sites/.assets-link-$$"
	rm -rf "$sites"/.assets-old-* 2>/dev/null || true
fi

[ "$(readlink "$sites/assets")" = "$target" ] || {
	echo "entrypoint: could not link $sites/assets to $target" >&2
	exit 1
}

exec "$@"
