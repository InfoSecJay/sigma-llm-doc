I'll analyze this Sigma rule for BloodHound/SharpHound detection and produce a structured investigation guide.

**Internal Analysis:**
- **Behavior**: Detection of BloodHound/SharpHound execution via process creation events using image names, company metadata, or command-line parameters specific to these AD enumeration tools.
- **Attack Lifecycle**: Post-breach reconnaissance phase; adversary has code execution and is mapping AD structure/relationships.
- **Telemetry Source**: Windows process creation logs (Event ID 4688, Sysmon Event ID 1).
- **What it doesn't prove**: Command-line obfuscation, lateral movement post-collection, or actual data exfiltration (only execution).
- **Evasion**: Binary renaming, parameter obfuscation, direct assembly loading, or execution via living-off-the-land binaries.

---

## Technical Context

This rule detects execution of BloodHound or SharpHound—post-breach Active Directory reconnaissance tools used to map domain structure, user relationships, group memberships, and privilege paths. The detection triggers on process creation events matching known binary names (Bloodhound.exe, SharpHound.exe), vendor metadata (SpecterOps, evil corp), or distinctive command-line parameters (e.g., `-CollectionMethod All`, `-JsonFolder`, `-ZipFileName`). The attacker objective is to enumerate the AD environment to identify high-value targets and privilege escalation paths before lateral movement or privilege elevation.

This maps to MITRE ATT&CK **T1087.001 (Account Discovery - Local Account)**, **T1087.002 (Account Discovery - Domain Account)**, **T1482 (Domain Trust Discovery)**, **T1069.001 (Permission Groups Discovery - Local Groups)**, **T1069.002 (Permission Groups Discovery - Domain Groups)**, and **T1059.001 (Command and Scripting Interpreter - PowerShell)**.

Primary telemetry sources are Windows Security Event ID 4688 (Process Creation) and Sysmon Event ID 1 (Process Create). Required fields include Image, CommandLine, Company, Description, and Product metadata. If malicious, this indicates an attacker with code execution attempting to build a complete AD attack surface map—a high-confidence precursor to privilege escalation or lateral movement.

**Critical limitation**: This detection does **not** confirm data exfiltration, lateral movement, or intent to weaponize findings. Legitimate security tools (Bloodhound Community Edition, authorized AD auditing) may trigger this rule.

---

## Investigation Steps

- **Confirm process execution context and timing**: Extract the parent process (ParentImage, ParentCommandLine) from Event ID 4688 or Sysmon Event ID 1. Verify whether execution originated from user session (explorer.exe, cmd.exe), scheduled task (tasksched.exe), Windows service, or remote execution (WinRM, PsExec). Malicious indicators include execution from temporary directories (C:\Windows\Temp, %APPDATA%), scheduled tasks with random names, or parent processes associated with malware (msiexec.exe with suspicious arguments, rundll32.exe, regsvcs.exe). Benign execution typically originates from security team workstations, scheduled security scans, or documented penetration testing windows.

- **Validate binary identity and source**: Cross-reference file hash (MD5, SHA256) against VirusTotal, internal threat intelligence, or known-good hashes from authorized security tool deployments. Check file metadata (digital signature, version info, creation time) using PowerShell `Get-Item` or Event Viewer file properties. Confirm file path matches known installations or golden images. Malicious indicators include unsigned or forged signatures, mismatched version info, file written to disk within minutes of execution, or binary located in non-standard paths (user temp, Downloads, %APPDATA%).

- **Analyze command-line parameters for collection scope and output**: Extract full CommandLine field and parse arguments such as `-CollectionMethod`, `-JsonFolder`, `-ZipFileName`, `--Loop`, and `--PortScanTimeout`. Verify whether output files were written to disk by checking file creation events (Sysmon Event ID 11 or Security Event ID 4656 for file access) in directories referenced by `-JsonFolder` or `-ZipFileName`. Collect file size and write timestamps. High-confidence malicious indicators include: output directed to hidden shares (C$, ADMIN$), network paths (\\\\attacker-server\\share), or credentials cached in the output JSON files; collection with `--Loop` for persistent enumeration; or use of `-PortScanTimeout` to enable network scanning.

- **Correlate with lateral movement and credential access**: Query proxy/firewall logs, network DNS, and Sysmon Event ID 3 (Network Connection) for outbound SMB (port 445), LDAP (389, 636), or Kerberos (88) traffic from the source host within 5–30 minutes post-execution. Cross-reference source user account with privilege escalation attempts (Event ID 4672, 4673), credential dumping (lsass.exe access via Event ID 3), or subsequent remote code execution (WinRM, WMI, lateral tool execution). Benign activity: isolated BloodHound execution with no follow-on network activity or privilege changes; activity during scheduled security assessments; restricted collection scope (e.g., `-CollectionMethod DCOnly`).

- **Identify user and asset context**: Determine whether the source user is a service account, security team member, or standard end-user. Check logon type (Event ID 4624) to confirm interactive (2), network (3), batch (4), or service (5) logon. Verify asset role: member workstation, server, domain controller, or jump box. Malicious indicators include: execution by low-privilege or inactive user accounts; execution on end-user workstations or production servers (unexpected); or logon initiated from untrusted network segment or VPN. Benign context: execution on security team workstations, admin workstations in sensitive asset groups, or monitored threat hunting systems.

- **Check for obfuscation and alternative execution paths**: Review CommandLine for evidence of parameter obfuscation (base64 encoding, variable substitution, reflection.assembly loading). Query Sysmon Event ID 7 (Image Load) for suspicious DLL loading (System.DirectoryServices.AccountManagement, LDAP libraries) without corresponding legitimate parent processes. Search process creation logs for variants (e.g., renamed executable, execution via PowerShell `-EncodedCommand`, execution via .NET reflection). Absence of obfuscation and transparent arguments favor benign activity; presence of heavy obfuscation, direct assembly loading, or living-off-the-land execution (PowerShell, cscript.exe) escalate confidence to malicious.

---

## Priority

**High.** BloodHound/SharpHound execution in an enterprise indicates an attacker with code execution performing strategic AD reconnaissance. This behavior is rarely legitimate outside controlled security assessments and is a nearly universal precursor to privilege escalation or lateral movement in ransomware, APT, and insider threat campaigns. Rapid triage is essential to prevent downstream attack progression.

---

## Blind Spots and Assumptions

**Detection assumes** process creation logging is enabled (audit policy: `AuditPolicyGUID {0cce923f-69ae-11d9-bed3-505054503030}`) and Sysmon or EDR is forwarding Event ID 1/4688 with full CommandLine telemetry. The rule does not detect: binary renaming (e.g., Enum.exe), direct assembly loading via PowerShell reflection (`[Reflection.Assembly]::LoadFile()`), or invocation via unmonitored .NET hosting processes. Legitimate red-teaming, authorized AD auditing tools, and native PowerShell AD cmdlets (`Get-ADUser`, `Get-ADGroupMember`) may trigger this rule if instrumented similarly. **Companion detections** that strengthen coverage: monitor for PowerShell `-EncodedCommand` execution with LDAP/AD namespaces; flag scheduled task creation with BloodHound-related parameters; detect ZIP file creation and network exfiltration in the same time window; alert on SMB/LDAP scanning patterns following process execution.

---

> **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team.