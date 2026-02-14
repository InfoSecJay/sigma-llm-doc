### Technical Context

This rule detects execution of BloodHound and SharpHound, widely used Active Directory reconnaissance tools that map attack paths by enumerating domain objects, group memberships, sessions, trusts, and ACLs. The detection targets distinctive command-line parameters, binary metadata (Product, Description, Company fields), and known executable names associated with these tools.

The attacker objective is Discovery-phase reconnaissance to identify privilege escalation paths, lateral movement opportunities, and high-value targets such as Domain Admins or Kerberoastable accounts. This maps to MITRE ATT&CK techniques T1087.001/T1087.002 (Account Discovery), T1482 (Domain Trust Discovery), T1069.001/T1069.002 (Permission Groups Discovery), and T1059.001 (PowerShell execution for Invoke-BloodHound). Primary telemetry is Windows process creation events (Security Event ID 4688 with command-line logging enabled, or Sysmon Event ID 1). Required fields include CommandLine, Image, Product, Description, and Company from PE metadata.

This detection confirms execution of a known offensive tool with AD enumeration intent. It does NOT confirm successful data collection, exfiltration of results, or that the collected data was used for subsequent attack phases. An attacker may have executed the tool but failed to retrieve usable output.

---

### Investigation Steps

- **Verify process metadata and execution context**: Examine Security Event ID 4688 or Sysmon Event ID 1 for the triggering process. Confirm the Image path, Product, Description, and Company fields match known SharpHound/BloodHound signatures. Check the parent process—legitimate IT tools would not spawn these binaries; common malicious parents include cmd.exe, powershell.exe, or C2 beacon processes.

- **Analyze command-line parameters for collection scope**: Review the exact CommandLine arguments to determine enumeration scope. Parameters like `-CollectionMethod All` or `DCOnly` indicate comprehensive domain enumeration. `--Loop --Loopduration` suggests persistent session monitoring. Document the `-d` (domain) parameter to identify targeted domains and whether child or trusted domains were included.

- **Identify output artifacts and staging behavior**: SharpHound outputs JSON files compressed into ZIP archives. Search for `-JsonFolder` and `-ZipFileName` parameters to locate output paths. Query file creation events (Sysmon Event ID 11) for *.zip files in the specified directory or common staging locations (%TEMP%, user profile directories, or network shares). Presence of these files confirms successful data collection.

- **Establish user and host context**: Determine the executing user account via the SubjectUserName field in Event ID 4688. Cross-reference with AD group membership—execution by a Domain Admin or service account on a non-administrative workstation is high-severity. Execution from a PAW, domain controller, or by a known red team account during an authorized engagement represents expected behavior.

- **Correlate with LDAP and network enumeration activity**: Query Directory Service logs (Event ID 1644 if enabled) or network traffic for high-volume LDAP queries originating from the source host within a 5-minute window. SharpHound generates distinctive LDAP filter patterns querying objectClass=user, objectClass=group, and objectClass=trustedDomain. Validate whether SMB session enumeration (Event ID 5145) occurred against multiple hosts.

- **Check for exfiltration or lateral movement indicators**: Search for outbound network connections from the source host to external IPs or cloud storage domains within 30 minutes post-execution. Query for subsequent authentication events (Event ID 4624 Type 3/10) from the same user to other hosts, which may indicate the attacker is acting on collected intelligence.

---

### Priority

High severity. BloodHound/SharpHound execution represents confirmed use of offensive tooling with no legitimate enterprise purpose outside sanctioned red team operations. This activity typically precedes privilege escalation or lateral movement within hours. Immediate containment evaluation is warranted unless correlated with an authorized penetration test.

---

### Blind Spots and Assumptions

Detection relies on command-line logging being enabled (Group Policy: Audit Process Creation and Include command line) and accurate PE metadata, which attackers may strip or modify via recompilation. Renamed binaries or custom SharpHound builds will evade image-name and metadata matching. PowerShell-based Invoke-BloodHound loaded reflectively via AMSI bypass may avoid process creation logs entirely. Complement this detection with LDAP query volume monitoring, anomalous Kerberos TGS requests for SPNs (T1558.003 detection), and file creation alerts for ZIP archives in user-writable directories.

---

> **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team.