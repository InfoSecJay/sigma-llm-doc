### Technical Context

This detection identifies execution of **BloodHound** or **SharpHound**, commonly used to enumerate Active Directory relationships and privilege paths. It triggers on known binaries, company metadata (SpecterOps), and command-line parameters such as `-CollectionMethod All`, `Invoke-Bloodhound`, `DCOnly`, `-JsonFolder`, and `-ZipFileName`. These parameters indicate structured AD data collection and staging.

The likely objective is domain privilege escalation mapping and attack path discovery. This aligns with MITRE ATT&CK techniques: **Account Discovery (T1087.001, T1087.002)**, **Domain Trust Discovery (T1482)**, **Permission Groups Discovery (T1069.001, T1069.002)**, and **Command and Scripting Interpreter – PowerShell (T1059.001)** under the Discovery and Execution tactics.

Primary telemetry is Windows process creation logs: **Security Event ID 4688** and/or **Sysmon Event ID 1**, including full command-line logging. If malicious, this indicates adversary reconnaissance preparing for lateral movement or privilege escalation. This detection does not confirm credential theft, exploitation, or privilege escalation occurred—only enumeration activity.

---

### Investigation Steps

* **Validate process creation telemetry:**
  Review **Security Event ID 4688** or **Sysmon Event ID 1** for `Image`, `ParentImage`, `CommandLine`, and `User`. Confirm execution of `SharpHound.exe`, `BloodHound.exe`, or PowerShell with `Invoke-Bloodhound` or `Get-BloodHoundData`. High-confidence malicious indicator: `-CollectionMethod All`, `DCOnly`, `--NoSaveCache`, or `-JsonFolder` combined with `-ZipFileName`.

* **Assess execution context and account:**
  Identify the `SubjectUserName` (4688) or `User` (Sysmon). Execution by standard domain users on workstations is high-risk. Execution by Tier 0 admins on DCs during maintenance windows may be legitimate. Flag service accounts or newly created accounts running enumeration tools.

* **Analyze parent process lineage:**
  Inspect `ParentProcessName` and `ParentCommandLine`. Suspicious parents include `cmd.exe`, `powershell.exe`, `wscript.exe`, or remote execution artifacts (e.g., `psexecsvc.exe`, `wmiprvse.exe`). Legitimate security assessments typically originate from known admin jump hosts or red team infrastructure.

* **Validate file staging artifacts:**
  If `-JsonFolder` or `-ZipFileName` is present, check filesystem telemetry (Sysmon Event ID 11) for creation of JSON files and ZIP archives in user-writable directories (e.g., `C:\Users\<user>\AppData\Local\Temp\`). Presence of large ZIP archives containing AD data is a high-confidence malicious indicator outside approved testing.

* **Correlate with domain controller activity:**
  Review **Directory Service logs**, **Security Event ID 4662**, and LDAP query telemetry from DCs for high-volume object reads from the source host. SharpHound often generates heavy LDAP traffic. Unusual LDAP enumeration from non-admin workstations strengthens suspicion.

* **Identify legitimate use cases:**
  Confirm with the security or red team if an authorized assessment is underway. Approved testing typically runs from controlled jump hosts, during scoped time windows, and may include documented ticket references. Absence of change control or ticketing increases risk.

---

### Priority

High severity. BloodHound enumeration is commonly weaponized in ransomware and post-compromise campaigns. If executed on production endpoints without authorization, it strongly indicates active domain reconnaissance.

---

### Blind Spots and Assumptions

Detection depends on process command-line visibility; disabled 4688 command-line logging or missing Sysmon reduces reliability. Adversaries may rename binaries or recompile SharpHound to evade string-based detection. Complement with LDAP enumeration volume analytics and abnormal AD object query monitoring to strengthen coverage.

---

> **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team.
