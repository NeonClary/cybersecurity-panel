from pathlib import Path

p = Path(r"C:\Users\dream\CCAI-Demo-Canvas-Upgrades\phd-advisor-frontend\src\components\canvas\canvasData.js")
c = p.read_text(encoding="utf-8")

start = c.index("export const INSIGHTS = [")
end = c.index("export const WIDGET_CATALOG")

insights = r'''export const INSIGHTS = [
  {
    id: 'i-progress',
    title: 'Program progress',
    icon: 'graph',
    category: 'progress',
    confidence: 82,
    summary: 'Zero Trust Phase 2 is 78% complete. MFA enforced for workforce; service accounts and legacy VPN exceptions remain the main gaps before audit sampling.',
    bullets: [
      'Identity: <strong>MFA 94%</strong> workforce · service accounts in remediation',
      'Network: micro-segmentation pilot on <strong>3 app tiers</strong>',
      '<strong>Risk:</strong> 12 VPN exceptions still lack compensating controls',
    ],
    pinned: true,
    sources: 18,
    updatedMinutesAgo: 5,
    quotes: [
      '"MFA rollout blocked on two legacy HR integrations." — IAM workstream notes',
      '"Auditors will sample VPN exception register first." — GRC advisor chat',
    ],
  },
  {
    id: 'i-method',
    title: 'Controls posture',
    icon: 'flask',
    category: 'theory',
    confidence: 71,
    summary: 'SOC 2 CC6/CC7 mappings are drafted. Detection use cases cover ransomware and cred theft; log retention and IR tabletop evidence are still thin.',
    bullets: [
      'Mapped: <strong>CC6.1–CC6.7</strong> access controls with Okta + AWS',
      'Open: centralized logging retention proof for <strong>365 days</strong>',
      'Open: tabletop scenario for <strong>ransomware + exfil</strong> not yet run',
    ],
    sources: 14,
    updatedMinutesAgo: 14,
    quotes: [
      '"Need SIEM retention screenshots before fieldwork." — compliance advisor',
      '"Tabletop scheduled but not executed." — IR lead notes',
    ],
  },
  {
    id: 'i-lit',
    title: 'Threat landscape',
    icon: 'book',
    category: 'literature',
    confidence: 76,
    summary: 'Strong coverage of identity attacks, SaaS misconfigurations, and supply-chain risks for your stack. Weaker on OT exposure and insider threat playbooks.',
    bullets: [
      '<strong>Coverage:</strong> MITRE techniques for cloud identity & SaaS',
      '<strong>Gap:</strong> limited intel on <strong>OAuth consent phishing</strong> variants',
      '<strong>Gap:</strong> no formal insider-threat escalation path documented',
    ],
    sources: 32,
    updatedMinutesAgo: 28,
    quotes: [
      '"OAuth abuse is the fastest-moving thread in your sector." — threat intel advisor',
      '"Insider playbook is a one-pager — not enough for audit." — GRC advisor',
    ],
  },
  {
    id: 'i-questions',
    title: 'Open security questions',
    icon: 'sparkles',
    category: 'theory',
    confidence: 63,
    summary: 'Three live threads. Q1 (scope of zero trust for contractors) gates architecture sign-off. Q2–Q3 affect detection engineering priorities.',
    bullets: [
      '<strong>Q1:</strong> Do contractors get full ZTNA or bastion-only access?',
      '<strong>Q2:</strong> Which SIEM detections are in-scope for SOC 2 evidence?',
      '<strong>Q3:</strong> Is customer data in EU regions in scope for DPA addendum?',
    ],
    sources: 9,
    updatedMinutesAgo: 41,
    quotes: [
      '"Contractor access model blocks network design." — architect advisor',
      '"EU data residency may expand audit scope." — privacy advisor',
    ],
  },
  {
    id: 'i-next',
    title: 'Next steps',
    icon: 'arrow',
    category: 'action',
    confidence: 85,
    summary: 'Near-term actions tied to audit date and production cutover. Two items have slipped one sprint.',
    bullets: [
      'Close <strong>12 VPN exceptions</strong> or document compensating controls',
      'Run ransomware tabletop & upload minutes to evidence locker',
      'Ship <strong>5 high-fidelity detections</strong> to production SIEM',
      'Finalize vendor SOC 2 bridge letter for subprocessors',
    ],
    sources: 7,
    updatedMinutesAgo: 9,
    quotes: [
      '"VPN exceptions are the #1 audit finding risk." — GRC advisor',
      '"Detections without tuning will false-positive in week one." — SOC advisor',
    ],
  },
  {
    id: 'i-blockers',
    title: 'Blockers & risks',
    icon: 'alert',
    category: 'risk',
    confidence: 74,
    summary: 'One technical blocker (legacy logging), one governance blocker (exception approvals). Governance is the higher audit risk.',
    bullets: [
      '<strong>Technical:</strong> legacy app logs not reaching SIEM — 18% of prod traffic',
      '<strong>Governance:</strong> exception approval SLA &gt; 10 days — auditors will flag',
    ],
    sources: 6,
    updatedMinutesAgo: 20,
    quotes: [
      '"Without those logs you cannot prove detective controls." — detection engineer',
      '"Exception backlog reads as control failure." — devil\'s advocate advisor',
    ],
  },
];

'''

p.write_text(c[:start] + insights + c[end:], encoding="utf-8")
print("insights updated")
