### Technical Context

This rule detects the execution of **BloodHound** or its ingestor, **SharpHound**, by monitoring process creation metadata and command-line arguments. These tools are the industry standard for mapping Active Directory (AD) attack paths, identifying overly permissive ACLs, and locating high-value targets like Domain Admins. The detection relies on specific string matches in the `CommandLine`, `Product`, or `Description` fields of Windows process logs.

The primary objective for an attacker using these tools is **Discovery (TA0007)**, specifically targeting **Domain Trust Discovery (T1482)** and **Account Discovery (T1087)**. Legitimate use is typically restricted to authorized red team engagements or periodic security audits by AD administrators. If triggered outside of a known maintenance window, this indicates an adversary is actively mapping the environment for lateral movement or privilege escalation.

This detection identifies the *tooling* used but does not confirm successful data exfiltration or that the adversary has gained elevated permissions. It tracks the initiation of the enumeration process, not the outcome of the LDAP queries or the subsequent analysis of the collected JSON data.

---

### Investigation Steps

* **Validate Process Metadata**: Examine **Security Event ID 4688** or **Sysmon Event ID 1** to inspect the `Company`, `Description`, and `Product` fields. Authentic SharpHound binaries often contain "SpecterOps" or "SharpHound" in these fields, though sophisticated actors may use renamed binaries or custom wrappers to evade simple string matches.
* **Analyze Command-Line Arguments**: Review the `CommandLine` field for flags like `-CollectionMethod All`, `-ZipFileName`, or `Invoke-Bloodhound`. Compare the execution time against the change management calendar; authorized audits are usually scheduled, whereas malicious execution often occurs from non-admin workstations or recently compromised service accounts.
* **Identify Originating User and Host**: Determine the security context of the process. Malicious activity often originates from a standard user account attempting to enumerate the entire domain, while legitimate administrative activity is more likely to originate from a designated management jump box or a Domain Controller (DC) using an "Admin" prefixed account.
* **Correlate with Network Telemetry**: Search for a spike in **LDAP/S (TCP 389/636)** or **SMB (TCP 445)** traffic originating from the suspect host immediately following the process start time. SharpHound generates significant volumes of traffic as it queries the DC and probes individual endpoints for active sessions.
* **Check for Artifact Staging**: Look for the creation of `.zip` or `.json` files in the user’s `TEMP` directory or the directory where the binary was executed (e.g., `20260213214619_BloodHound.zip`). The presence of these files, followed by their removal or move to a network share, is a high-confidence indicator of completed data staging for exfiltration.

---

### Priority

**High.** BloodHound is a "pre-exploitation" tool that is almost universally weaponized by ransomware operators and advanced persistent threats (APTs) to find the shortest path to Domain Admin. An alert on a production workstation indicates an adversary has already bypassed initial defenses and is preparing for widespread impact.

---

### Blind Spots and Assumptions

* **Evasion via Obfuscation**: Attackers can easily bypass this rule by renaming the binary, modifying the source code to change internal metadata, or using PowerShell "in-memory" execution with obfuscated function names.
* **Telemetry Requirements**: This detection assumes robust logging of process command lines (Command Line Process Auditing) is enabled via GPO or an EDR solution.
* **Companion Detection**: To strengthen coverage, monitor for **Event ID 4662** (Operation performed on an object) with a high frequency of LDAP queries originating from a single source, which detects the underlying behavior rather than just the tool name.

Would you like me to generate a hunt query for the specific LDAP traffic patterns associated with this tool?