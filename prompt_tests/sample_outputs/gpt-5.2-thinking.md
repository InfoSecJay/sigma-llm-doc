### Technical Context

This alert fires on **Windows process creation telemetry** when a process image or PE metadata matches **BloodHound/SharpHound** (e.g., `Bloodhound.exe`, `SharpHound.exe`, Product/Description containing *SharpHound*, Company containing SpecterOps) or when the **command line** contains known BloodHound/SharpHound collection flags (e.g., `-CollectionMethod All`, `--CollectionMethods Session`, `--Loop`, `DCOnly`, `Invoke-Bloodhound`, `Get-BloodHoundData`, `-JsonFolder` + `-ZipFileName`). The typical attacker objective is **Active Directory reconnaissance** to map users, groups, sessions, computers, ACLs, and trust paths for **lateral movement and privilege escalation planning**.

Relevant MITRE ATT&CK mappings include **Discovery** (e.g., *Account Discovery* **T1087.001/T1087.002**, *Permission Groups Discovery* **T1069.001/T1069.002**, *Domain Trust Discovery* **T1482**) and often **Execution** via PowerShell (*Command and Scripting Interpreter: PowerShell* **T1059.001**) when invoked through `Invoke-Bloodhound` / `Get-BloodHoundData`. Primary telemetry is **process creation** from **Windows Security Event ID 4688** and/or **Sysmon Event ID 1** (plus EDR process events) with strong reliance on **Image**, **CommandLine**, **ParentImage/ParentCommandLine**, and (if populated) **Company/Product/Description** fields from file version info.

If malicious, the impact is significant: it indicates an adversary (or operator) is actively enumerating AD relationships to accelerate privilege escalation paths. This detection **does not confirm compromise or credential theft** on its own—it confirms *execution intent* (collector invocation) but not whether collection succeeded, what scope was reached, or whether data was exfiltrated/imported into BloodHound.

---

### Investigation Steps

* **Validate the exact collector invocation and scope**: In **Security 4688 / Sysmon 1**, capture `Image`, `CommandLine`, `ParentImage`, `ParentCommandLine`, `User`, `LogonId`. Treat as higher risk when you see **broad/automated scope** flags such as `-CollectionMethod All`, `--CollectionMethods Session`, `--Loop --Loopduration`, `DCOnly`, or `--NoSaveCache` (operator attempting to reduce artifacts). Benign runs are usually time-bound, run-once, and documented (no looping) by IT security teams.

* **Identify a high-confidence malicious indicator in the parent chain**: Escalate immediately if the parent/launch pattern is **PowerShell-driven collection** such as `Invoke-Bloodhound` / `Get-BloodHoundData` (seen in `CommandLine` and/or `ParentCommandLine` in **4688/Sysmon 1**) executed by a **non-admin user** or from suspicious parents (e.g., `winword.exe` → `powershell.exe` → `SharpHound.exe`). This chain is uncommon for legitimate AD health checks and is a strong signal of hands-on-keyboard activity.

* **Hunt for collector output staging on disk**: If **Sysmon Event ID 11 (FileCreate)** is available (or EDR file events), pivot from the process `ProcessGuid`/`ProcessId` to look for creation of **JSON output folders** and **zip archives** consistent with `-JsonFolder` and `-ZipFileName`. High-signal artifacts include `.json` bursts in a short window and a resulting `.zip` placed in user-writable locations (e.g., `%TEMP%`, `%APPDATA%`, `Downloads`, `Desktop`) rather than sanctioned assessment paths.

* **Correlate expected network behaviors of SharpHound collection**: If **Sysmon Event ID 3 (NetworkConnect)**, firewall logs, or EDR network telemetry exist, correlate the collector process to connections toward **domain controllers and endpoints** commonly used for collection (e.g., LDAP **389/636**, SMB **445**, RPC **135**, WinRM **5985/5986**, ADWS **9389**). Malicious indicators include broad fan-out to many hosts in minutes, connections from unusual subnets/segments, or a workstation contacting DCs it normally never queries at that volume.

* **Determine whether this is legitimate security testing or unauthorized discovery**: Legitimate activity typically has **known operator accounts**, **change tickets**, **approved tooling locations**, and execution from **admin/jump hosts** or designated assessment systems. Validate `User`/`SubjectUserName` (4688), host role (workstation vs admin server), and whether the binary is in an approved path and signed/allowed per your EDR allowlists. An unsanctioned run on a standard user workstation or server outside the security tooling enclave is not normal.

* **Check for downstream handling and possible exfiltration of collected data**: If a `.zip` is created, pivot to proxy/DNS/network logs for the same host/user for **immediate outbound transfer** shortly after creation (common staging→exfil workflow). Focus on large uploads, unusual destinations, or interactive file transfer tooling. Collection without subsequent staging/exfil is still serious, but staging + outbound transfer materially increases confidence and urgency.

---

### Priority

Treat as **High** by default because BloodHound/SharpHound is widely weaponized for AD discovery and pathfinding, and successful collection can rapidly enable privilege escalation and lateral movement. Severity should be **Critical** if executed on a tier-0 asset (DC/admin jump host) or by an untrusted user/account with evidence of output staging (`-JsonFolder`/`-ZipFileName`) or rapid host/DC fan-out.

---

### Blind Spots and Assumptions

This logic is **brittle to evasion**: binaries can be renamed, flags can be altered, collectors can run in-memory, and PowerShell can be obfuscated—reducing command-line fidelity. Reliable detection assumes **4688 with command-line auditing enabled** and/or **Sysmon 1** (plus enriched fields like `Company/Product/Description`), which many environments lack consistently. Strengthen coverage with companion detections for **AD enumeration at scale** (LDAP/query volume anomalies to DCs), **SharpHound-like file creation bursts** (Sysmon 11), and **collector-associated network fan-out** (Sysmon 3 / firewall telemetry) tied to the same process and host.

---

> **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team.
