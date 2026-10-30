#!/bin/bash
# factory_reset.sh - return this Raspberry Pi to its first-start state.
#
# Run it after handing in your work:
#
#   sudo ~/Assembly-with-Raspberry-PI-5/factory_reset.sh            reset
#   sudo ~/Assembly-with-Raspberry-PI-5/factory_reset.sh --dry-run  only list what it would delete
#
# It erases every user's files (this project, the photo, the notebook,
# downloads, browser sessions, histories), the saved Wi-Fi networks, the
# packages installed with "apt install", the logs and caches, and the
# machine's identity. The next time the Pi starts, it shows the welcome
# wizard (country, user, password, Wi-Fi), as a new Raspberry Pi does.
#
# How: it copies itself to /usr/local/sbin and reboots. The erasing runs
# early in the next start, before anyone can log in; then the Pi powers off.
# The wizard is set up with rename-user, the official tool of Raspberry Pi
# OS (package userconf-pi), which renames user 1000 to the new user.

set -u

SELF=/usr/local/sbin/factory-reset-run
UNIT=/etc/systemd/system/factory-reset.service
DRY=0

die() { echo "factory_reset: $*" >&2; exit 1; }

# Run a command, or only print it with --dry-run.
run() {
    if [ "$DRY" = 1 ]; then echo "  would run: $*"; else "$@"; fi
}

first_user() { getent passwd 1000 | cut -d: -f1; }

# People's accounts other than user 1000 (the wizard renames that one):
# users with their home in /home. System accounts are never touched.
other_users() {
    awk -F: '$3 > 1000 && $3 < 60000 && $6 ~ /^\/home\// { print $1 }' /etc/passwd
}

# Packages installed with "apt install" / "apt-get install" after the date
# of the system image (/etc/rpi-issue), read from apt's history. Packages
# that came with the image, system updates ("apt upgrade") and the packages
# the welcome wizard installs are not listed, so the kernel and the
# firmware are never removed. Without the image date, nothing is listed.
installed_packages() {
    local image_date logs=() f
    image_date=$(grep -s -m1 -o '[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}' /etc/rpi-issue)
    [ -n "$image_date" ] || return
    for f in /var/log/apt/history.log*; do [ -e "$f" ] && logs+=("$f"); done
    [ ${#logs[@]} -eq 0 ] && return
    zcat -f "${logs[@]}" | awk -v image_date="$image_date" '
        /^Start-Date:/ { after = ($2 > image_date) }
        /^Commandline:/ { manual = after && ($0 ~ /apt(-get)? .*install/) }
        /^Install:/ && manual {
            sub(/^Install: /, "")
            n = split($0, parts, /\), /)
            for (i = 1; i <= n; i++) { split(parts[i], w, ":"); print w[1] }
        }
        /^$/ { manual = 0; after = 0 }' |
        grep -vE '^(linux-|raspi-firmware|raspberrypi-|firmware-|rpi-eeprom)' |
        sort -u |
        while read -r pkg; do
            # Only installed packages, never the ones the system needs
            # (essential, or priority required, important or standard).
            dpkg-query -W -f='${Status}|${Essential}|${Priority}\n' "$pkg" 2>/dev/null |
                grep -q '^install ok installed|[^|]*|\(optional\|extra\)$' &&
                echo "$pkg"
        done
}

# ---------------------------------------------------------------------------
# Step 1 (sudo ./factory_reset.sh): check, ask, and schedule the reset.
# ---------------------------------------------------------------------------
prepare() {
    [ "$(id -u)" = 0 ] || die "run it with sudo: sudo $0"
    grep -qs "Raspberry Pi" /proc/device-tree/model || die "this is not a Raspberry Pi."
    [ -x /usr/bin/rename-user ] || die "rename-user is missing (package userconf-pi)."
    local fu; fu=$(first_user)
    [ -n "$fu" ] || die "there is no user 1000 for the welcome wizard to rename."

    echo "This erases EVERYTHING students left on this Raspberry Pi:"
    echo
    echo "  - all the files of user '$fu' (the project, the photo, the notebook,"
    echo "    downloads, browser sessions, histories)"
    local u; for u in $(other_users); do echo "  - user '$u' and all its files"; done
    local nets; nets=$(ls /etc/NetworkManager/system-connections/ 2>/dev/null)
    [ -n "$nets" ] && echo "  - saved networks: $(echo $nets | sed 's/\.nmconnection//g')"
    local pkgs; pkgs=$(installed_packages)
    [ -n "$pkgs" ] && echo "  - packages installed with apt install: $(echo $pkgs)"
    echo "  - logs, caches, temporary files, SSH keys and the machine's identity"
    echo
    echo "Then the Pi powers off. The next time it starts, it shows the welcome"
    echo "wizard, as a new Raspberry Pi."

    if [ "$DRY" = 1 ]; then
        echo
        echo "--dry-run: nothing was changed. These are the steps of the reset:"
        erase
        return
    fi

    echo
    echo "Hand in your work BEFORE continuing: it cannot be recovered."
    read -r -p "Type ERASE to continue, anything else to cancel: " answer
    [ "$answer" = "ERASE" ] || { echo "Cancelled. Nothing was changed."; exit 0; }

    # The repository is erased too, so the second step runs from a copy.
    install -m 0755 "$(readlink -f "$0")" "$SELF"
    cat > "$UNIT" <<EOF
[Unit]
Description=Factory reset (erase all user data, then power off)
DefaultDependencies=no
After=local-fs.target systemd-journald.service
Before=getty@tty1.service lightdm.service display-manager.service ssh.service
ConditionPathExists=$SELF

[Service]
Type=oneshot
ExecStart=$SELF --erase
StandardOutput=journal+console
StandardError=journal+console
TimeoutStartSec=infinity

[Install]
WantedBy=sysinit.target
EOF
    systemctl daemon-reload
    systemctl enable factory-reset.service >/dev/null 2>&1 || die "could not schedule the reset."
    sync
    echo "Restarting to erase. The Pi powers off by itself when it finishes:"
    echo "do not unplug it before that."
    sleep 3
    reboot
}

# ---------------------------------------------------------------------------
# Step 2 (early in the next start, as root): erase, set up the wizard, power off.
# ---------------------------------------------------------------------------
erase() {
    local fu; fu=$(first_user)
    local fg; fg=$(id -gn "$fu")
    echo "factory reset: erasing..."

    # Packages first, while apt's history still lists them. apt simulates the
    # removal first: if it would also remove any package outside the list
    # (something the system needs), no package is removed.
    local pkgs extra; pkgs=$(installed_packages)
    if [ -n "$pkgs" ]; then
        # shellcheck disable=SC2086  # one argument per package
        extra=$(apt-get -s purge $pkgs 2>/dev/null | awk '/^(Purg|Remv) / { print $2 }' |
                grep -vxF -f <(printf '%s\n' $pkgs))
        if [ -n "$extra" ]; then
            echo "  not removing packages: it would also remove $(echo $extra)"
        elif [ "$(echo "$pkgs" | wc -l)" -gt 150 ]; then
            echo "  not removing packages: $(echo "$pkgs" | wc -l) is too many for what a student installs"
        else
            # shellcheck disable=SC2086
            run apt-get purge -y -q $pkgs
        fi
    fi
    run apt-get clean

    # Users: delete the extra ones, and empty user 1000 (the wizard renames
    # it and sets the new password). Until then nobody can log in as it.
    local u
    for u in $(other_users) rpi-first-boot-wizard; do
        getent passwd "$u" >/dev/null && run userdel -r -f "$u"
    done
    run rm -f /etc/sudoers.d/010_wiz-nopasswd
    run rm -rf "/home/$fu"
    run install -d -m 0700 -o "$fu" -g "$fg" "/home/$fu"
    run cp -a /etc/skel/. "/home/$fu/"
    run chown -R "$fu:$fg" "/home/$fu"
    run passwd -l "$fu"
    run usermod -s /usr/sbin/nologin "$fu"
    local d
    for d in /home/*; do
        [ "$d" = "/home/$fu" ] || [ ! -e "$d" ] || run rm -rf "$d"
    done
    run rm -rf /root/.bash_history /root/.cache /root/.config /root/.local /root/.ssh
    run rm -rf /var/spool/cron/crontabs/*

    # Networks, Bluetooth pairings, SSH.
    run rm -rf /etc/NetworkManager/system-connections/*
    run rm -rf /var/lib/NetworkManager/*
    run rm -rf /var/lib/bluetooth/*
    run systemctl disable ssh
    run rm -f /etc/ssh/ssh_host_*
    run ssh-keygen -A
    [ "$(hostname)" = raspberrypi ] || run raspi-config nonint do_hostname raspberrypi

    # Temporary files, logs and the machine's identity (systemd makes a new
    # one at the next start).
    run find /tmp /var/tmp -mindepth 1 -delete
    run journalctl --rotate
    run journalctl --vacuum-time=1s
    run find /var/log -type f \( -name '*.gz' -o -name '*.[0-9]' -o -name '*.old' \) -delete
    run find /var/log -type f -exec truncate -s 0 {} +
    run truncate -s 0 /etc/machine-id
    [ -L /var/lib/dbus/machine-id ] || run rm -f /var/lib/dbus/machine-id

    # The welcome wizard, the official way: full wizard for user 1000.
    run env SUDO_USER="$fu" /usr/bin/rename-user -f -s

    # Remove this script and its service, then power off.
    run systemctl disable factory-reset.service
    run rm -f "$UNIT" "$SELF"
    run sync
    echo "factory reset: done."
}

case "${1:-}" in
    --dry-run) DRY=1; [ "$(id -u)" = 0 ] || die "run it with sudo: sudo $0 --dry-run"; prepare ;;
    --erase)   erase; systemctl poweroff ;;
    "")        prepare ;;
    *)         die "unknown option '$1'. Use: sudo $0 [--dry-run]" ;;
esac
