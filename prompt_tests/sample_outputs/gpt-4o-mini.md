  ### Technical Context
  This rule detects the execution of known command-line arguments associated with the BloodHound and SharpHound tools, commonly used for Active Directory enumeration and privilege escalation. Attackers employ these tools to map relationships and permissions within an AD environment, allowing them to identify high-privilege accounts and potential attack paths. The objective is often to advance their access rights within a network by exploiting trust relationships and user permissions that are more granular than what traditional reconnaissance methods may reveal.

  Relevant MITRE ATT&CK tactics and techniques include:
  - **Discovery** (TA0007)
    - Active Directory Enumeration (T1087.001)
    - Account Discovery (T1087.002)
  - **Execution** (TA0002)
    - Command and Scripting Interpreter (T1059.001)
  - **Credential Access** (TA0006)
    - Credential Dumping (T1069.001)
    - Domain Trusts (T1069.002)

  Primary data sources for detection include:
  - Process creation events from endpoint telemetry, which provide insights into executed commands and parameters.
  - System logs that can highlight any unusual access or usage patterns related to BloodHound or SharpHound.

  ### Investigation Steps
  - **Review Process Creation Logs:** Analyze the process execution logs for any instances of BloodHound.exe or SharpHound.exe, focusing on command-line arguments that match the known suspicious patterns.
  - **Analyze Command-Line Arguments:** Investigate command-line parameters that were executed to determine the exact nature of the enumeration being performed, especially concerning collection methods and potential session grabs.
  - **Check for Related Network Activity:** Monitor network logs for suspicious traffic patterns, particularly those indicating lateral movement or external reconnaissance connected to the execution of these tools.
  - **Correlate with User and System Behavior:** Assess user behavior and system logs to identify if the execution corresponds with unusual access attempts or changes in user privileges linked to the tool's objectives.

  ### Prioritization
  Given its capabilities to reveal sensitive information about user privileges and relationships within Active Directory, this alert is classified as high severity. The use of BloodHound or SharpHound typically indicates a targeted reconnaissance phase of an attack, increasing the urgency for investigation.

  ### Blind Spots and Assumptions
  Detection coverage may be limited by non-standard command-line usage or the execution of scripts that make use of similar arguments used by legitimate applications. The detection logic assumes that logs for process creation are enabled and adequately captured, including command-line details. If the command line is not fully recorded due to system configurations, this may lead to missed detections of malicious activity. Additionally, legitimate software that uses similar command-line parameters may generate false positives if not distinguishable from actual threats.

  > **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team.
