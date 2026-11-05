# Shared init helper. BusyBox accepts --retry but does not implement waiting.
stop_chromax_daemon() {
    pidfile=$1
    executable=$(readlink -f "$2")
    if [ ! -f "$pidfile" ]; then return 0; fi
    pid=$(cat "$pidfile")
    case "$pid" in ''|*[!0-9]*) echo 'Invalid service PID'; return 1;; esac
    [ "$pid" -gt 1 ] || return 1
    if [ "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$executable" ]; then
        kill -TERM "$pid" 2>/dev/null || true
        count=0
        while [ "$count" -lt 100 ] && [ "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$executable" ]; do
            sleep 0.1
            count=$((count + 1))
        done
        if [ "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$executable" ]; then
            kill -KILL "$pid" 2>/dev/null || true
            sleep 0.2
        fi
        if [ "$(readlink "/proc/$pid/exe" 2>/dev/null)" = "$executable" ]; then return 1; fi
    fi
    rm -f "$pidfile"
}
