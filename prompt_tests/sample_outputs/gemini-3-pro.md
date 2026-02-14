### Technical Context

This rule detects the execution of SharpHound, the data collector for BloodHound, or BloodHound itself, based on process metadata and specific command-line arguments. Adversaries utilize BloodHound to map Active Directory (AD) trust relationships, identify session information, and calculate the shortest attack paths to high-value targets like Domain Admin. This activity falls under the Discovery tactic, specifically Domain Trust Discovery (T1482), Account Discovery (T1087), and Permission Groups Discovery (T1069).

The primary telemetry source is Windows Process Creation logs (Security Event ID 4688 or Sysmon Event ID 1). If confirmed malicious, this indicates an attacker has established a foothold and is actively performing reconnaissance to facilitate lateral movement or privilege escalation. This detection confirms the tool's execution attempts but does not inherently prove that data exfiltration or successful privilege escalation has already occurred.

### Investigation Steps

* **Analyze Process Metadata and Parentage**: Review the process creation event (Event ID 4688/Sysmon 1). Verify if the `Image`, `Description`, or `Company` fields match known defaults like "SpecterOps" or "evil corp" (a common default in compiled SharpHound binaries). Identify the Parent Process; execution via `cmd.exe`, `powershell.exe`, or unknown binaries in temporary directories (e.g., `%TEMP%`, `Downloads`) indicates manual execution or dropper activity.
* **Examine Command Line Arguments**: scrutinize the `CommandLine` field for enumeration scopes. Arguments like `-CollectionMethod All`, `--Loop`, or `-d [Domain]` indicate an intent to map the entire domain structure. The presence of `Invoke-Bloodhound` suggests execution via a PowerShell script rather than a standalone binary.
* **Correlate with Network Traffic (LDAP/SMB/RPC)**: BloodHound generates a high volume of traffic. Check Firewall or Network Connection logs (Sysmon Event ID 3) for a single host initiating massive LDAP (TCP/389, TCP/636) queries to Domain Controllers or RPC/SMB (TCP/445, TCP/135) connections to a wide range of workstations within a short timeframe (Session enumeration).
* **Verify File Creation Artifacts**: SharpHound typically outputs results to a compressed archive or JSON files. Search File Creation logs (Sysmon Event ID 11) for files matching the patterns `*_BloodHound.zip`, `*.json`, or the directory specified by the `-JsonFolder` argument. Presence of these files confirms successful data collection.
* **Validate User Context and Authorization**: Determine if the executing user has a legitimate business need for AD auditing (e.g., Domain Admins or Internal Audit). Cross-reference the timestamp with authorized Red Team engagements or vulnerability scanning schedules. Execution by a standard user, service account, or `SYSTEM` is a high-confidence malicious indicator.

### Priority

This alert represents a **High** priority incident. BloodHound is the industry standard for AD attack path management; unauthorized execution implies an attacker has compromised a host and is aggressively mapping the network to plan lateral movement. While the tool itself is non-destructive, it is a precursor to high-impact actions like Domain Admin compromise.

### Blind Spots and Assumptions

* **In-Memory Execution**: Competent adversaries may load SharpHound directly into memory (e.g., via Cobalt Strike `execute-assembly`), potentially bypassing process creation logs if command-line auditing is not granular or if arguments are obfuscated.
* **Custom Builds**: Attackers can recompile SharpHound to modify metadata (Company, Description) and rename the binary, evading static string detection; however, behavioral patterns (LDAP volume) usually remain.
* **Companion Detections**: This rule should be paired with detections for "High Volume of LDAP Queries" or "Rapid SMB Session Enumeration" to cover evasion attempts where the binary footprint is masked.

---

> **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team.