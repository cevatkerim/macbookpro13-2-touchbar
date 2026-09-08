# Touch ID failure after repeated lock-screen timeouts

Experimental local patch for T1Bridge 0.1.4. During a long Omarchy lock session,
fingerprint scans timed out every ten seconds. Each scan stopped and restarted
the keybag relay. Eventually the relay failed to activate, then load, the
biometric keybag; all fingerprint consumers returned errors, including polkit.
Saved enrollment records were still present and password login worked.

The original relay reloads and promotes the saved biometric keybag on every
restart. This patch first checks the live bag. If present and unlocked, it must
accept the saved secret and pass a lock-state readback. Only an explicit
not-found reply takes the original cold restore path. Rejected secrets,
unexpected state and protocol errors fail startup without reloading the bag.
Fingerprint matching and PAM remain separate and unchanged.

A bounded diagnostic run recovered relay readiness on the affected machine
without rebooting or replacing private state. This supports avoiding repeated
keybag replacement; the precise cause inside Apple's firmware is unconfirmed.
The persistent service override is installed. Twenty-five spaced service
restarts, a real right-index-finger match, and sixteen consecutive ten-second
scans cancelled through fprintd all passed. Every cancellation recovered the
relay within five seconds; fprintd reported no errors during that final run.
The Touch Bar authentication prompt was also visible. Restart tests use normal
intervals to respect systemd's start limit. A subsequent 51-second lock session
completed five fingerprint PAM sessions, recorded successful authentication,
and unlocked without starting a password PAM session. A capture of the live
Touch Bar frame confirmed the normal controls returned. After a subsequent
reboot, the patched keybag service was active and the owner reported Touch ID
working. Suspend/resume remains untested.

Local checks: Rust formatting, Clippy, workspace tests, native tests and
sanitizers, kernel builds and packaging checks passed. The complete
`make -k quality` run reported one unavailable check: dependency policy, because
`cargo-deny` is not installed. This patch adds no dependencies.

## Build and install

These instructions target the pinned T1Bridge 0.1.4 source. Review compatibility
before using another release. Run build commands as your normal user. From the
root of this repository:

```bash
fix_repo="$PWD"
build_root="$(mktemp -d)"
git clone https://github.com/standardagents/t1bridge.git "$build_root/t1bridge"
cd "$build_root/t1bridge"
git checkout --detach cbfb191487330e48dc77f266049c6d1cd08461c5
git apply --check "$fix_repo/integrations/keybag-relay/reuse-live-keybag.patch"
git apply "$fix_repo/integrations/keybag-relay/reuse-live-keybag.patch"
make quality
cargo build --release -p t1-daemons --bin t1-keybag-relay --features keybag-relay-service
```

`make quality` requires the upstream development tools, including `cargo-deny`.
Check its full output. Tests for this patch cover warm reuse, cold restoration,
secret rejection, invalid state, malformed replies and resource cleanup.

Install from a visible terminal where you can enter your password:

```bash
sudo install -Dm755 target/release/t1-keybag-relay \
  /usr/local/libexec/t1bridge-patches/t1-keybag-relay
sudo install -Dm644 "$fix_repo/integrations/keybag-relay/10-reuse-live-keybag.conf" \
  /etc/systemd/system/t1bridge-keybag.service.d/10-reuse-live-keybag.conf
sudo systemctl daemon-reload
sudo systemctl restart t1bridge-keybag.service
systemctl is-active t1bridge-keybag.service
fprintd-verify
```

Require an actual `verify-match`, then test a lock session longer than several
scan timeouts and confirm both fingerprint and password unlock. Do not erase
enrollment, keybag or xART data to recover this error.

The system service override survives reboot and retains the packaged service's
sandbox settings. It also survives package upgrades: review and remove it when
installing an upstream version that addresses this behavior. The package binary
is preserved at `/usr/lib/t1bridge/t1-keybag-relay`.

## Roll back

```bash
sudo systemctl stop t1bridge-keybag.service
sudo rm /etc/systemd/system/t1bridge-keybag.service.d/10-reuse-live-keybag.conf
sudo systemctl daemon-reload
sudo systemctl start t1bridge-keybag.service
```

This restores the packaged executable. If it still cannot load the keybag,
stop that service to end the retry loop and use password authentication while
investigating. Rolling back the executable does not repair failed firmware state.
