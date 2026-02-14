### Technical Context

This rule detects the execution of **BloodHound** or **SharpHound**, specialized reconnaissance tools used to map Active Directory (AD) attack paths. Attackers use these tools to identify complex permission chains, such as "GPO Local Admin" or "Unconstrained Delegation," that allow for lateral movement and privilege escalation toward Domain Admin rights.

The behavior typically occurs during the **Discovery** phase (MITRE ATT&CK T1087, T1482, T1069) or via **PowerShell Execution** (T1059.001). It relies on heavy LDAP querying and SAMR (Security Account Manager Remote) enumeration. The primary telemetry source is **Windows Process Creation (Event ID 4688 or Sysmon Event ID 1)**, specifically monitoring the `CommandLine`, `Product`, and `Company` fields.

A successful execution allows an adversary to visualize the shortest path to domain compromise. This detection confirms that a tool *associated* with BloodHound was invoked, but it does not confirm if the tool successfully successfully bypassed local AV/EDR or if the data was successfully exfiltrated from the host.

---

### Investigation Steps

* **Verify Process Metadata and Signatures:** Examine **Security Event ID 4688** or **Sysmon Event ID 1**. Check the `Company` and `Description` fields for "SpecterOps" or "SharpHound." Legitimate administrative tools rarely use these strings; their presence indicates a high-confidence match for the tool.
* **Analyze Command Line Arguments:** Look for specific flags like `-CollectionMethod All`, `--ZipFileName`, or `Invoke-Bloodhound`. Malicious usage often includes `--NoSaveCache` to minimize the local footprint or `--Loop` to maintain persistent visibility of active sessions.
* **Identify Origin and Parent Process:** Determine how the tool was launched. Execution via `powershell.exe`, `cmd.exe`, or a non-standard service (e.g., a scheduled task or PsExec) is highly suspicious. Check **Sysmon Event ID 7** (Image Loaded) to see if `SharpHound.exe` loaded unexpected .NET reflection assemblies.
* **Inspect Local Artifacts and Staging:** Search the filesystem for `.zip` or `.json` files created by the process (e.g., `20240101120000_BloodHound.zip`). SharpHound typically stages data in the current working directory or `\Temp\`. Use **Sysmon Event ID 11** (FileCreate) to identify where the data was gathered for exfiltration.
* **Baseline Against Admin Activity:** Check if the user is a member of the Domain Admins or an authorized IT audit group. Legitimate use is usually restricted to specific "jump boxes" or admin workstations during scheduled security assessments or "purple team" exercises.
* **Correlate with Network Telemetry:** Cross-reference the timestamp with a spike in outbound LDAP (Port 389/636) or SMB (Port 445) traffic from the source host to Domain Controllers. High volumes of LDAP queries from a standard workstation are a primary indicator of active AD enumeration.

---

### Priority

**High.** BloodHound is the industry-standard tool for identifying domain escalation paths and is a precursor to ransomware deployment or mass data theft. An alert on a non-admin workstation or a high-value server (e.g., SQL or Web) should be treated as a critical "hands-on-keyboard" incident.

---

### Blind Spots and Assumptions

Attackers can easily evade this rule by renaming the binary, stripping metadata, or using custom "wrappers" that obfuscate command-line arguments. This detection assumes process-level logging is enabled and fails if the attacker uses in-memory execution techniques like Cobalt Strike's `execute-assembly` without a discernible command line. To strengthen coverage, monitor for **LDAP Search Filter** anomalies (Event ID 1644) or **Honeytoken** account access.

---

> **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team.

Would you like me to generate a corresponding hunting query for your EDR to supplement this detection?