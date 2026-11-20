export type Role = "EXECUTOR" | "COORDINATOR" | "HEAD" | "ANALYST" | "ADMIN"
export type MeasureStatus =
  "DRAFT" | "PLANNED" | "IN_PROGRESS" | "ON_REVIEW" | "RETURNED" | "DONE" | "PARTIAL" | "NOT_DONE"
export type FlagType =
  | "OVERDUE"
  | "NO_EVIDENCE"
  | "FORMAL_CLOSURE"
  | "WORSENING"
  | "AWAITING_EFFECT"
  | "VAGUE_RESULT"
  | "TARGET_MISSED"
  | "REPEATED_DELAY"
  | "REPEATED_POSTPONEMENT"
  | "DATE_OUT_OF_PERIOD"
  | "BACKDATED_EVIDENCE"
  | "NO_EXPLANATION"
  | "PREMATURE_DESCRIPTION"
export type FlagStatus = "OPEN" | "RESOLVED"
export type RecStatus = "PROPOSED" | "ACCEPTED" | "REJECTED" | "DONE"
export type Decision = "APPROVED" | "RETURNED"
export type Channel = "IN_APP" | "EMAIL" | "MESSENGER"
export type ReportType = "NAZK" | "PRINT" | "INTERNAL"
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
export type ProgramStatus = "DRAFT" | "APPROVED" | "ARCHIVED"
export type MeasureAction = "progress" | "submit" | "uploadEvidence" | "edit" | "approve" | "return"
export type Decimal = string | number

export interface User {
  id: string
  displayName: string
  role: Role
  orgUnitId: string
}

export interface UserWithToken extends User {
  token: string
  tokenExpiresAt?: string | null
}

export interface LoginResult extends User {
  expiresAt: number
}

export interface UserRef {
  id: string
  displayName: string
  role: Role
}

export interface OrgUnit {
  id: string
  name: string
  parentId: string | null
}

export interface IndicatorValue {
  id: string
  value: Decimal
  measuredAt: string
  sampleSize?: number | null
  sourceEvidenceId: string | null
}

export interface Indicator {
  id: string
  name: string
  unit: string
  baseline: Decimal
  target: Decimal
  riskId: string | null
  current: Decimal | null
  isImproved: boolean
  isTargetReached: boolean
  values: IndicatorValue[]
}

export interface RiskRef {
  id: string
  code: string
  description: string
  level: RiskLevel
}

export interface Risk extends RiskRef {
  indicators: Indicator[]
  programId?: string | null
  probability?: number | null
  impact?: number | null
  score?: number | null
  process?: string
  content?: string
  sources?: string
  existingControls?: string
  ownerUnitId?: string | null
  ownerUnitName?: string | null
  measureCount?: number
}

export interface RiskKriIn {
  name: string
  unit: string
  direction?: "LOWER" | "HIGHER" | null
  baseline: number
  target: number
  targetDate?: string | null
  source: string
  independent: boolean
}

export interface RiskCreate {
  code: string
  description: string
  programId?: string | null
  probability: number
  impact: number
  process: string
  content: string
  sources: string
  existingControls: string
  ownerUnitId?: string | null
  indicator?: RiskKriIn | null
}

export interface Program {
  id: string
  title: string
  orgUnitId: string
  periodStart: string
  periodEnd: string
  hasRestrictedInfo: boolean
  status: ProgramStatus
}

export interface FlagBrief {
  id: string
  type: FlagType
  explanation: string
  status: FlagStatus
}

export interface MeasureListItem {
  id: string
  code: string
  title: string
  sectionNumber: number
  isPermanent: boolean
  plannedDeadline: string
  deadline: string
  period: string | null
  status: MeasureStatus | null
  isOverdue: boolean
  daysLeft: number
  risk: RiskRef | null
  responsibleUnit: string | null
  responsibleUser: string | null
  openFlags: FlagBrief[]
  evidenceCount: number
}

export interface NonExecutionRisk {
  level: RiskLevel
  reasons: string[]
}

export interface MeasureWithRisk extends MeasureListItem {
  nonExecutionRisk: NonExecutionRisk
}

export interface Assignment {
  orgUnitId: string
  userId: string | null
  isResponsible: boolean
  orgUnitName: string
  userName: string | null
}

export interface MeasurePeriod {
  id: string
  period: string
  status: MeasureStatus
  actualDate: string | null
  resultDescription: string | null
  nonExecutionReason: string | null
}

export interface Evidence {
  id: string
  period: string
  fileName: string
  contentType: string
  size: number
  objectKey: string
  sha256: string
  version: number
  uploadedAt: string
  uploadedBy: string | null
  docType: string
  documentDate: string | null
}

export interface EvidenceFile {
  file: File
  docType: string
  documentDate: string | null
}

export interface DeadlineChange {
  id: string
  decidedOn: string
  oldDeadline: string
  newDeadline: string
  reason: string
  decidedByName: string | null
  createdAt: string
}

export interface ProgressUpdate {
  id: string
  statusFrom: MeasureStatus
  statusTo: MeasureStatus
  text: string
  createdAt: string
  author: UserRef | null
}

export interface Approval {
  id: string
  decision: Decision
  comment: string
  createdAt: string
  reviewer: UserRef | null
}

export interface RiskFlag {
  id: string
  measureId: string
  measureCode: string
  measureTitle: string
  type: FlagType
  ruleCode: string
  facts: Record<string, unknown>
  explanation: string
  status: FlagStatus
  createdAt: string
  resolvedAt: string | null
  resolutionComment: string | null
}

export interface MeasureDetail extends MeasureListItem {
  sectionTitle: string
  programId: string
  requiredEvidence: string
  indicatorText: string
  indicator: Indicator | null
  internalDeadline: string | null
  deadlineChanges: DeadlineChange[]
  assignments: Assignment[]
  periods: MeasurePeriod[]
  currentPeriod: MeasurePeriod | null
  updates: ProgressUpdate[]
  approvals: Approval[]
  evidence: Evidence[]
  flags: RiskFlag[]
  allowedActions: MeasureAction[]
}

export interface SubmitResult {
  measure: MeasureDetail
  hints: string[]
}

export interface AssignmentIn {
  orgUnitId: string
  userId?: string | null
  isResponsible: boolean
}

export interface MeasureIn {
  sectionId: string
  code: string
  title: string
  isPermanent: boolean
  plannedDeadline: string
  riskId?: string | null
  indicatorText: string
  indicatorUnit: string
  indicatorTarget: number | string | null
  requiredEvidence: string
  assignments: AssignmentIn[]
}

export interface SectionPassport {
  id: string
  number: number
  title: string
  measures: MeasureListItem[]
}

export interface ProgramPassport extends Program {
  orgUnitName: string
  sections: SectionPassport[]
  totals: Record<string, number>
}

export interface Recommendation {
  id: string
  flagId: string | null
  measureId: string | null
  measureTitle: string | null
  text: string
  basis: {
    rule?: string
    ruleDescription?: string
    flagType?: FlagType
    explanation?: string
    facts?: Record<string, unknown>
    riskLevel?: RiskLevel
    priority?: number
    source?: string
    [key: string]: unknown
  }
  responsibleId: string | null
  dueDate: string | null
  status: RecStatus
  createdAt: string
}

export interface Reminder {
  id: string
  measureId: string
  measureTitle: string
  sendAt: string
  channel: Channel
  text: string
  sent: boolean
}

export interface AuditEntry {
  id: number
  user: UserRef | null
  entity: string
  entityId: string | null
  action: string
  oldValue: Record<string, unknown> | null
  newValue: Record<string, unknown> | null
  at: string
  prevHash: string
  hash: string
}

export interface AuditVerify {
  ok: boolean
  checked: number
  firstBrokenId: number | null
}

export interface JobResult {
  flagsOpened: number
  flagsAutoResolved: number
  recommendationsCreated: number
  remindersCreated: number
  periodsStarted: number
}

export interface Report {
  id: string
  programId: string
  period: string
  type: ReportType
  fileKey: string | null
  generatedAt: string
  revokedAt: string | null
  revokeReason: string
}

export interface NazkMeasureRow {
  measureId: string
  code: string
  title: string
  executors: string
  plannedDeadline: string
  actualDeadline: string | null
  state: string
  resultOrReason: string
  corruptionRisk: string | null
  indicator: string | null
}

export interface NazkReport {
  reportId: string
  programTitle: string
  orgUnit: string
  period: string
  periodEnd: string
  hasRestrictedInfo: boolean
  sections: { number: number; title: string; measures: NazkMeasureRow[] }[]
}

export interface ReturnedItem {
  measure: MeasureListItem
  comment: string
}

export interface ExecutorDashboard {
  upcoming: MeasureWithRisk[]
  returned: ReturnedItem[]
  overdue: MeasureListItem[]
  reminders: Reminder[]
  totalMine: number
}

export interface SectionProgress {
  number: number
  title: string
  total: number
  byStatus: Record<MeasureStatus, number>
  donePercent: number
  overdue: number
}

export interface CalendarItem {
  date: string
  measureId: string
  code: string
  title: string
  status: MeasureStatus | null
  isOverdue: boolean
}

export interface ReportReadiness {
  period: string
  total: number
  ready: number
  percent: number
  missing: MeasureListItem[]
}

export interface CoordinatorDashboard {
  programId: string
  reviewQueue: MeasureListItem[]
  flagsByType: Record<FlagType, number>
  openFlags: RiskFlag[]
  progressBySection: SectionProgress[]
  calendar: CalendarItem[]
  reportReadiness: ReportReadiness
}

export interface Overall {
  total: number
  byStatus: Record<MeasureStatus, number>
  donePercent: number
  overdue: number
  risksTotal: number
  risksReduced: number
  openFlags: number
}

export interface RiskState {
  id: string
  code: string
  description: string
  level: RiskLevel
  measuresTotal: number
  measuresDone: number
  indicators: Indicator[]
  reduced: boolean
}

export interface UnitCell {
  orgUnitId: string
  name: string
  total: number
  overdue: number
  openFlags: number
  level: RiskLevel
  reasons: string[]
}

export interface ExecutiveDashboard {
  programId: string
  overall: Overall
  critical: MeasureWithRisk[]
  risks: RiskState[]
  units: UnitCell[]
  upcomingDeadlines: CalendarItem[]
  recommendations: Recommendation[]
  flagsByType: Record<FlagType, number>
}

export interface UnitDashboard {
  orgUnitId: string
  name: string
  cell: UnitCell
  measures: MeasureWithRisk[]
}

export interface Dictionaries {
  sections: { number: number; title: string }[]
  flagRules: { type: FlagType; ruleCode: string; description: string }[]
  [key: string]: unknown
}

export type SignalType =
  | "TARGET_NOT_REACHED"
  | "INSUFFICIENT_DATA"
  | "BASELINE_CHANGED"
  | "INCIDENT_FLOOR"
  | "REASSESS_UP"
  | "REASSESS_DOWN"
  | "PRIORITY_VIOLATION"
  | "RISK_DISPLACEMENT"
  | "EFFECT_NOT_CONFIRMED"

export type SignalColor = "red" | "orange" | "yellow" | "gray" | "green"

export interface Kri {
  indicatorId: string
  name: string
  unit: string
  direction: "LOWER" | "HIGHER"
  weight: number
  lagMonths: number
  source: string
  independent: boolean
  baseline: number
  target: number
  targetDate: string | null
  current: number | null
  measuredAt: string | null
  sampleSize: number | null
  minSample: number | null
  delta: number
  change: number | null
  noise: boolean
  raw: number | null
  p: number | null
  selfReportDiscount: boolean
  expected: number | null
  state: KriState
  stateLabel: string
  insufficient: string[]
  pairedWith: string | null
  baselineFrozenAt: string | null
  baselineChanged: boolean
}

export type KriState = "ON_TRACK" | "LAGGING" | "NO_CHANGE" | "WORSENING" | "NO_DATA"

export type RiskVerdict =
  "WORKING" | "FORMAL" | "WORSE_DESPITE" | "EXTERNAL" | "STAGNANT" | "UNATTENDED" | "NO_DATA" | "NO_MEASURES"

export interface MeasureState {
  measureId: string
  code: string
  title: string
  section: number
  status: MeasureStatus | null
  done: boolean
  pending: boolean
  completedOn: string | null
}

export interface ReassessmentHint {
  rule: "P1" | "L+1" | "L-1"
  text: string
  suggested: number
  inputs: Record<string, unknown>
  source: string
}

export interface RiskSignal {
  id: string | null
  riskId: string
  riskCode: string
  indicatorId: string | null
  indicatorName: string | null
  type: SignalType
  ruleCode: string
  label: string
  color: SignalColor
  facts: Record<string, unknown>
  explanation: string
  status: FlagStatus
  createdAt: string | null
}

export interface Incident {
  id: string
  riskId: string
  occurredOn: string
  confirmed: boolean
  source: string
  description: string
  createdAt: string
}

export interface RiskAssessment {
  riskId: string
  code: string
  description: string
  level: RiskLevel
  asOf: string
  rulesetVersion: string
  probability0: number
  impact0: number
  inherent: number
  inherentLevel: RiskLevel
  kris: Kri[]
  rrs: number | null
  rrsCategory: string
  expected: number | null
  effect: KriState
  effectLabel: string
  measures: MeasureState[]
  doneCount: number
  verdict: RiskVerdict
  verdictLabel: string
  verdictColor: SignalColor
  preliminary: boolean
  effectDue: string | null
  hints: ReassessmentHint[]
  signals: RiskSignal[]
  incidents: Incident[]
}

export interface RiskBrief {
  code: string
  rrs: number | null
  contributionPp: number | null
}

export interface RiskModelOverview {
  programId: string
  asOf: string
  rulesetVersion: string
  pri: number
  exec: number
  fcg: number
  fcgColor: SignalColor
  topContributor: RiskBrief | null
  weakestLink: RiskBrief | null
  subIndex: number | null
  subIndexCount: number
  scopeName?: string | null
  verdictCounts: Record<RiskVerdict, number>
  risksWithDone: number
  risksWorking: number
  uncovered: UncoveredRisk[]
  risks: RiskAssessment[]
}

export interface UncoveredRisk {
  riskId: string
  code: string
  description: string
  level: RiskLevel
  probability0: number
  impact0: number
  inherent: number
}

export interface AnalyticsKpis {
  measuresTotal: number
  done: number
  notDone: number
  overdue: number
  onReview: number
  returned: number
  donePercent: number
  onTimePercent: number
  evidenceCoveragePercent: number
  returnRatePercent: number
  avgReviewDays: number | null
  risksTotal: number
  risksReduced: number
  openFlags: number
  recommendationsProposed: number
  recommendationsAccepted: number
}

export interface StatusPoint {
  date: string
  counts: Record<MeasureStatus, number>
}

export interface FlagPoint {
  date: string
  opened: number
  resolved: number
  open: number
}

export interface AnalyticsOverview {
  programId: string
  programTitle: string
  asOf: string
  period: string
  kpis: AnalyticsKpis
  statusTrend: StatusPoint[]
  flagTrend: FlagPoint[]
  risks: RiskDynamics[]
  flagsByType: Record<string, number>
}

export interface IndicatorSeries {
  id: string
  name: string
  unit: string
  baseline: string | number
  target: string | number
  current: string | number | null
  progressPercent: number | null
  isImproved: boolean
  isTargetReached: boolean
  values: { date: string; value: string | number }[]
}

export interface RiskDynamics {
  id: string
  code: string
  description: string
  level: RiskLevel
  measuresTotal: number
  measuresDone: number
  reduced: boolean
  formalClosures: number
  indicators: IndicatorSeries[]
}

export interface Verdict {
  level: "good" | "attention" | "behind"
  title: string
  text: string
}

export interface AnalyticsSummary {
  programId: string
  programTitle: string
  period: string
  asOf: string
  total: number
  done: number
  inWork: number
  onReview: number
  overdue: number
  notDone: number
  due: number
  donePercent: number
  onTimePercent: number
  risksTotal: number
  risksReduced: number
  verdict: Verdict
  sections: { number: number; title: string; total: number; done: number; overdue: number; percent: number }[]
  upcoming: {
    measureId: string
    code: string
    title: string
    deadline: string
    daysLeft: number
    unit: string | null
  }[]
  upcomingTotal: number
  attention: string[]
  scope: string | null
}

export interface PerfCounters {
  tasks: number
  done: number
  onTime: number
  lateDone: number
  notDone: number
  partial: number
  overdue: number
  inWork: number
  onReview: number
  submissions: number
  returns: number
  decisions: number
  firstPass: number
  evidence: number
  openFlags: number
  delayDaysTotal: number
  delayed: number
  donePercent: number
  onTimePercent: number
  returnRate: number
  firstPassPercent: number
  avgDelayDays: number | null
}

export interface UnitPerformance extends PerfCounters {
  orgUnitId: string | null
  name: string
  people: number
}

export interface PersonPerformance extends PerfCounters {
  userId: string
  name: string
  role: Role
  orgUnitId: string
  orgUnit: string
  active: boolean
  lastActivity: string | null
}

export interface ReviewerPerformance {
  userId: string
  name: string
  reviews: number
  approved: number
  returned: number
  returnRate: number
  avgReviewDays: number | null
}

export interface TaskRow {
  measureId: string
  periodId: string
  code: string
  title: string
  section: number
  period: string
  status: MeasureStatus
  deadline: string
  actualDate: string | null
  delayDays: number | null
  onTime: boolean | null
  overdue: boolean
  orgUnitId: string | null
  orgUnit: string | null
  executors: string[]
  executorIds: string[]
  submissions: number
  returns: number
  evidence: number
  openFlags: FlagType[]
  riskCode: string | null
  lastActivity: string | null
}

export interface TaskEvent {
  kind: "submitted" | "approved" | "returned"
  at: string
  measureId: string
  code: string
  title: string
  period: string
  orgUnitId: string | null
  orgUnit: string | null
  actorId: string | null
  actor: string | null
  executorId: string | null
  executor: string | null
  comment: string
  round: number | null
  resolved: boolean | null
}

export interface PerformanceReport {
  programId: string
  programTitle: string
  asOf: string
  period: string | null
  periods: string[]
  orgUnitId: string | null
  userId: string | null
  scope: string | null
  totals: PerfCounters
  units: UnitPerformance[]
  people: PersonPerformance[]
  reviewers: ReviewerPerformance[]
  tasks: TaskRow[]
  events: TaskEvent[]
}

export interface ReportIntegrity {
  reportId: string
  sha256: string
  signature: string
  signedOn: string
  algorithm: string
  verifyUrl: string
  qrSvg: string
}

export interface ReportVerification {
  valid: boolean
  reason: string
  reportId: string | null
  period: string | null
  type: ReportType | null
  programTitle: string | null
  orgUnit: string | null
  generatedAt: string | null
  generatedBy: string | null
  sha256: string | null
  supersededBy: string | null
  supersededAt: string | null
  revokedAt: string | null
  revokeReason: string | null
}

export interface ReportCopyCheck {
  match: boolean
  reason: string
  reportId: string | null
  format: string | null
  issuedAt: string | null
  period: string | null
  type: ReportType | null
  programTitle: string | null
}

export type DraftSource = "document" | "rule" | "model"
export type AnswerSource = "model" | "rule"
export type EntityType = "risk" | "indicator" | "measure" | "period" | "flag" | "signal" | "evidence" | "recommendation"

export interface AiStatus {
  enabled?: boolean
  reachable: boolean
  ready: boolean
  chatModel: string
  embedModel: string
  models: string[]
}

export interface AiSettings {
  enabled: boolean
  available: boolean
}

export interface MeasureCandidate {
  measureId: string
  code: string
  title: string
  period: string
  score: number
  reason: string
}

export interface ReportDraft {
  measureId: string | null
  period: string | null
  measureSource: DraftSource | null
  candidates: MeasureCandidate[]
  outcome: "done" | "not_done" | null
  outcomeSource: DraftSource | null
  text: string
  textSource: DraftSource
  documentText: string
  hints: string[]
  warnings: string[]
  fileName: string
  fileSha256: string
  draftKey: string | null
  model: string
  modelUsed: boolean
  disclaimer: string
}

export interface ReportDraftWithFile extends ReportDraft {
  file: File
}

export interface DraftField {
  value: string | number | boolean | null
  source: DraftSource
  documentValue: string
}

export interface MeasureDraftValues {
  sectionId: string | null
  code: string
  title: string
  isPermanent: boolean
  plannedDeadline: string | null
  riskId: string | null
  indicatorText: string
  indicatorUnit: string
  indicatorTarget: Decimal | null
  requiredEvidence: string
  assignments: AssignmentIn[]
}

export interface MeasureDraft {
  measure: MeasureDraftValues
  fields: Record<string, DraftField>
  warnings: string[]
  similar: { measureId: string; code: string; title: string; score: number }[]
  fileName: string
  model: string
  modelUsed: boolean
  disclaimer: string
}

export interface SourceRef {
  n: number
  type: EntityType
  id: string
  label: string
  target?: string | null
}

export interface RiskExplanation {
  riskId: string
  text: string
  textSource: AnswerSource
  references: SourceRef[]
  ruleText: string
  model: string
  modelUsed: boolean
  disclaimer: string
}

export interface DigestHighlights {
  pri: number
  priBefore: number
  exec: number
  execBefore: number
  done: number
  overdue: number
  newOverdue: number
  newFlags: number
  openFlags: number
  risksUp: number
  risksDown: number
}

export interface WeeklyDigest {
  programId: string
  since: string
  asOf: string
  text: string
  textSource: AnswerSource
  references: SourceRef[]
  ruleText: string
  highlights: DigestHighlights
  model: string
  modelUsed: boolean
  disclaimer: string
}

export interface EvidenceCheck {
  periodId: string
  findings: { ruleCode: string; ok: boolean; text: string; facts: Record<string, unknown> }[]
  unreadable: string[]
  advice: string
  adviceSource: AnswerSource | null
  quotes: { evidenceId: string; fileName: string; quote: string }[]
  model: string
  modelUsed: boolean
  disclaimer: string
}

export interface AskAnswer {
  answer: string
  answerSource: AnswerSource
  references: SourceRef[]
  model: string
  modelUsed: boolean
  disclaimer: string
}

export interface AiChatMessage {
  id: number
  role: "user" | "assistant"
  content: string
  answerSource: AnswerSource | null
  references: SourceRef[]
  model: string | null
  modelUsed: boolean | null
  createdAt: string
}

export interface AiChatSummary {
  id: string
  title: string
  messageCount: number
  createdAt: string
  updatedAt: string
}

export interface AiChat extends AiChatSummary {
  messages: AiChatMessage[]
  disclaimer: string
}

export interface CoverageGap {
  ruleCode: "C1" | "C2" | "C3"
  level: RiskLevel | null
  riskId: string | null
  riskCode: string | null
  measureId: string | null
  measureCode: string | null
  facts: Record<string, unknown>
  explanation: string
}

export interface AiSuggestion {
  recommendationId: string
  model: string
  text: string
  steps: string[]
  rationale: string
  disclaimer: string
  basis: Record<string, unknown>
}

export interface PeerStats {
  name: string
  orgUnit: string
  sharedMeasures: number
  tasks: number
  done: number
  overdue: number
  returns: number
  donePercent: number | null
  onTimePercent: number | null
  returnRate: number | null
  firstPassPercent: number | null
  avgDelayDays: number | null
}

export interface PeerReport {
  programTitle: string
  asOf: string
  sharedMeasures: number
  me: PeerStats
  average: PeerStats | null
  colleagues: number
  minGroup: number
}

export type InboxState = "NEW" | "LINKED" | "REJECTED"
export type OutboxState = "PENDING" | "SENT" | "FAILED" | "SUPERSEDED"

export interface IntegraInboxItem {
  id: string
  externalId: string
  title: string
  description: string
  component: string | null
  catalogNumber: string | null
  owner: string
  dueDate: string | null
  externalStatus: string | null
  state: InboxState
  measureId: string | null
  measureCode: string | null
  measureTitle: string | null
  reportedStatus: string | null
  rejectReason: string | null
  decidedBy: string | null
  decidedAt: string | null
  receivedAt: string
  updatedAt: string
}

export interface IntegraOutboxMessage {
  id: string
  inboxId: string | null
  title: string | null
  status: string | null
  state: OutboxState
  attempts: number
  lastError: string | null
  createdAt: string
  nextAttemptAt: string
  sentAt: string | null
}

export interface IntegraStatus {
  enabled: boolean
  targetUrl: string
  inbox: Record<InboxState, number>
  outbox: Record<OutboxState, number>
}

export interface DeliveryResult {
  sent: number
  failed: number
  pending: number
}
