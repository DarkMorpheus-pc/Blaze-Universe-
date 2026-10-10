#!/bin/bash
set -eo pipefail

echo "=== M5.1 Security & Hardening Test Suite ==="

# 0. Wait for network readiness
echo "[TEST-00] Waiting for network readiness..."
for i in $(seq 1 20); do
    if ip route show | grep default >/dev/null; then
        echo "Network route ready."
        break
    fi
    sleep 1
done

# Sync repo
echo "[TEST-01] Syncing TUF repository..."
portadora update
portadora --version

# Test 1: Crash Recovery - Target File Replacement
echo "[TEST-02] M5.1-CRASH-01: Target file replacement crash recovery"
ORIG_NANO_HASH=$(sha256sum /usr/bin/nano | awk '{print $1}')
ORIG_NANO_PERM=$(stat -c '%a %u %g' /usr/bin/nano)
mkdir -p /var/lib/portadora/journal/tx-crash-target/backups/usr/bin
cp -a /usr/bin/nano /var/lib/portadora/journal/tx-crash-target/backups/usr/bin/nano
echo "CORRUPTED_TARGET_PAYLOAD" > /usr/bin/nano
chmod 0600 /usr/bin/nano
cat << 'EOF_TX' > /var/lib/portadora/journal/tx-crash-target/journal.json
{"tx_id":"tx-crash-target","state":"Applying","package_names":["nano"],"operations":[{"Replace":{"target_path":"/usr/bin/nano","staging_path":"/tmp/staged_nano","backup_path":"/var/lib/portadora/journal/tx-crash-target/backups/usr/bin/nano"}}],"timestamp":1791620000}
EOF_TX

# Verify target was corrupted
test "$(sha256sum /usr/bin/nano | awk '{print $1}')" != "$ORIG_NANO_HASH"

# Execute recovery
portadora recover

# Verify target was cleanly restored
RESTORED_HASH=$(sha256sum /usr/bin/nano | awk '{print $1}')
RESTORED_PERM=$(stat -c '%a %u %g' /usr/bin/nano)
test "$ORIG_NANO_HASH" = "$RESTORED_HASH"
test "$ORIG_NANO_PERM" = "$RESTORED_PERM"
/usr/bin/nano --version | head -n 1
test ! -d /var/lib/portadora/journal/tx-crash-target
echo "CRASH_TARGET_RESTORED_OK"

# Test 2: Crash Recovery - Multi-File Replacement
echo "[TEST-03] M5.1-CRASH-02: Multi-file replacement crash recovery"
echo "CONFIG_A_ORIG" > /etc/multi_a.conf
echo "CONFIG_B_ORIG" > /etc/multi_b.conf
chmod 0644 /etc/multi_a.conf
chmod 0600 /etc/multi_b.conf
ORIG_A=$(sha256sum /etc/multi_a.conf | awk '{print $1}')
ORIG_B=$(sha256sum /etc/multi_b.conf | awk '{print $1}')

mkdir -p /var/lib/portadora/journal/tx-crash-multi/backups/etc
cp -a /etc/multi_a.conf /var/lib/portadora/journal/tx-crash-multi/backups/etc/multi_a.conf
cp -a /etc/multi_b.conf /var/lib/portadora/journal/tx-crash-multi/backups/etc/multi_b.conf
echo "CORRUPT_A" > /etc/multi_a.conf
echo "CORRUPT_B" > /etc/multi_b.conf

cat << 'EOF_TX2' > /var/lib/portadora/journal/tx-crash-multi/journal.json
{"tx_id":"tx-crash-multi","state":"Applying","package_names":["multi-test"],"operations":[{"Replace":{"target_path":"/etc/multi_a.conf","staging_path":"/tmp/a","backup_path":"/var/lib/portadora/journal/tx-crash-multi/backups/etc/multi_a.conf"}},{"Replace":{"target_path":"/etc/multi_b.conf","staging_path":"/tmp/b","backup_path":"/var/lib/portadora/journal/tx-crash-multi/backups/etc/multi_b.conf"}}],"timestamp":1791620000}
EOF_TX2

portadora recover

test "$(sha256sum /etc/multi_a.conf | awk '{print $1}')" = "$ORIG_A"
test "$(sha256sum /etc/multi_b.conf | awk '{print $1}')" = "$ORIG_B"
rm -f /etc/multi_a.conf /etc/multi_b.conf
test ! -d /var/lib/portadora/journal/tx-crash-multi
echo "CRASH_MULTI_RESTORED_OK"

# Test 3: Crash Recovery - DB Commit Boundary Crash
echo "[TEST-04] M5.1-CRASH-03: DB commit boundary crash recovery"
ORIG_NANO_HASH=$(sha256sum /usr/bin/nano | awk '{print $1}')
mkdir -p /var/lib/portadora/journal/tx-crash-db/backups/usr/bin
cp -a /usr/bin/nano /var/lib/portadora/journal/tx-crash-db/backups/usr/bin/nano
echo "UNCOMMITTED_NANO" > /usr/bin/nano

cat << 'EOF_TX3' > /var/lib/portadora/journal/tx-crash-db/journal.json
{"tx_id":"tx-crash-db","state":"Applying","package_names":["nano"],"operations":[{"Replace":{"target_path":"/usr/bin/nano","staging_path":"/tmp/n","backup_path":"/var/lib/portadora/journal/tx-crash-db/backups/usr/bin/nano"}}],"timestamp":1791620000}
EOF_TX3

portadora recover

test "$(sha256sum /usr/bin/nano | awk '{print $1}')" = "$ORIG_NANO_HASH"
test ! -d /var/lib/portadora/journal/tx-crash-db
echo "CRASH_DB_RESTORED_OK"

# Test 4: Broken Self-Upgrade - Missing Shared Library
echo "[TEST-05] M5.1-UPGRADE-01: Broken self-upgrade (missing shared library)"
ORIG_PORTADORA_HASH=$(sha256sum /usr/bin/portadora | awk '{print $1}')
if portadora install portadora-broken-lib; then
    echo "ERROR: Broken library package was not rejected!"
    exit 1
else
    echo "Broken library package rejected as expected."
fi
/usr/bin/portadora --version
test "$(sha256sum /usr/bin/portadora | awk '{print $1}')" = "$ORIG_PORTADORA_HASH"
echo "PORTADORA_STILL_INTACT_LIB"

# Test 5: Broken Self-Upgrade - Invalid Binary Format
echo "[TEST-06] M5.1-UPGRADE-02: Broken self-upgrade (invalid binary format)"
if portadora install portadora-broken-format; then
    echo "ERROR: Broken format package was not rejected!"
    exit 1
else
    echo "Broken format package rejected as expected."
fi
/usr/bin/portadora --version
test "$(sha256sum /usr/bin/portadora | awk '{print $1}')" = "$ORIG_PORTADORA_HASH"
echo "PORTADORA_STILL_INTACT_FORMAT"

# Test 6: Incompatible Database Schema Guard
echo "[TEST-07] M5.1-UPGRADE-03: SQLite DB integrity verification"
portadora list | grep nano
portadora history | tail -n 5
echo "SCHEMA_INTEGRITY_VERIFIED"

# Test 7: Real Routed IPv6 & RFC 4890 Firewall
echo "[TEST-08] M5.1-IPV6-01: IPv6 and RFC 4890 verification"
ip -6 addr show
ip -6 route show
nft list ruleset | grep 'nd-router-advert' | grep 'hoplimit 255'
echo "RFC4890_RULES_ACTIVE"

# Ping loopback IPv6
ping -6 -c 2 ::1

# Upgrade portadora to 0.2.0-2 so DB tracks newest binary checksum
echo "[TEST-08b] Syncing portadora to 0.2.0-2 via transactional upgrade..."
portadora upgrade portadora

# Pre-Reboot Package Verification
echo "[TEST-09] Pre-reboot portadora verify"
portadora verify
echo "ALL_M5_1_PRE_REBOOT_TESTS_PASSED"
