### Technical Context

This rule detects execution of BloodHound/SharpHound, Active Directory reconnaissance tools used by attackers and red teams to map AD trust relationships, group memberships, sessions, ACLs, and attack paths. SharpHound is the C# data collector; BloodHound is the graph-based analysis frontend. Detection fires on process metadata (image name, product/company fields) and characteristic command-line arguments such as `-CollectionMethod All`, `--Loop`, `Invoke-Bloodhound`, and output staging flags like `-JsonFolder`/`-ZipFileName`.

This maps to MITRE ATT&CK Discovery (TA0007) — specifically Account Discovery: Local/Domain (T1087.001/T1087.002), Domain Trust Discovery (T1482), and Permission Groups Discovery (T1069.001/T1069.002) — as well as Execution via PowerShell (T1059.001). The primary telemetry is Windows process creation events (Sysmon Event ID 1 or Security Event ID 4688 with command-line auditing enabled). Detection requires that image metadata fields (Product, Description, Company) are populated, which depends on Sysmon configuration or EDR enrichment.

If confirmed malicious, this indicates an attacker is actively enumerating AD to identify privilege escalation and lateral movement paths — typically a precursor to domain compromise. This rule does **not** confirm data exfiltration, exploitation of discovered paths, or whether the operator is an authorized red team.

---

### Investigation Steps

- **Verify the executing user and context**: Check the account name, logon session type, and originating host in Sysmon Event ID 1 or Security 4688. SharpHound run under a standard domain user on a workstation outside a scheduled pentest window is high-confidence malicious. Legitimate use is almost exclusively from authorized red team or IT security accounts on designated jump boxes.

- **Inspect the full command line for collection scope**: Look for `-CollectionMethod All` (full AD enumeration), `DCOnly` (targeting domain controllers via LDAP/replication), or `--Loop` (continuous session collection). `All` or `DCOnly` indicate broad reconnaissance; `Session` with `--Loop` suggests the operator is waiting to map active admin sessions for lateral movement targeting.

- **Check for staged output files**: SharpHound writes JSON files and compresses them into a ZIP (flags `-JsonFolder`, `-ZipFileName`, default pattern `*_BloodHound.zip` or `*_SharpHound.zip`). Search for file creation events (Sysmon Event ID 11) in the user's temp directory or the path specified. Presence of these ZIP artifacts confirms successful data collection.

- **Correlate with LDAP and network telemetry**: SharpHound generates heavy LDAP query traffic to domain controllers (ports 389/636). Check Directory Service Access logs (Security Event ID 4662) or network flow data for a burst of LDAP connections from the source host. A single workstation issuing thousands of LDAP queries in minutes is anomalous and corroborates the alert.

- **Assess for data exfiltration**: After collection, the operator must move the ZIP to the BloodHound GUI (typically off-network). Review proxy logs, SMB file transfers (Sysmon Event ID 17/18), or EDR network telemetry for outbound transfers of ZIP files from the source host shortly after the alert timestamp.

- **Determine if authorized testing is underway**: Check with the red team or offensive security program for active engagements scoped to this host/user. Legitimate pentest activity should be logged in an engagement tracker and use designated accounts. Absence of a corresponding engagement record escalates this to a confirmed incident.

---

### Priority

High. BloodHound/SharpHound execution on a domain-joined host is one of the most reliable indicators of active AD attack path reconnaissance and is a standard step in nearly every domain compromise playbook. Outside confirmed red team operations, this should be treated as an active intrusion requiring immediate containment assessment.

---

### Blind Spots and Assumptions

Detection relies on recognizable binary metadata or unobfuscated command-line strings; attackers frequently rename the binary, strip PE metadata, or run SharpHound reflectively in memory via `Execute-Assembly` (Cobalt Strike) where no process creation event with these indicators is generated. Command-line logging must be enabled (GPO or Sysmon) — without it, `selection_cli_*` conditions are blind. Complement this rule with LDAP query volume anomaly detection and Sysmon named pipe or .NET assembly load monitoring (Event ID 7, `clrjit.dll` loads in unusual processes) to catch in-memory execution variants.

---

> **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team.