export interface ScoringConfig {
  target_low: number
  target_high: number
  symmetry_max_diff: number
  angle_tolerance: number
  smooth_alpha: number
}

export interface DebugData {
  primary_angle: number | null
  knee_left: number | null
  knee_right: number | null
  target_angle: number | null
  deviation: number | null
  knee_diff: number | null
  symmetry_max_diff: number | null
  temporal_rhythm_cv: number | null
  temporal_smoothness: number | null
  angular_velocity: number | null
}

export interface ScoreData {
  total: number
  angle: number
  temporal: number
  symmetry: number
}

export interface ErrorData {
  name: string
  severity: number
  message: string
  suggestion: string
  joints?: number[]
}

export interface GuidanceData {
  type: string
  text: string
  priority: number
}

/** AI coach diagnosis from LLM two-stage output (<diagnosis> XML block). */
export interface DiagnosisData {
  root_cause?: string
  confidence?: number
  affected_joints?: string[]
  recommended_cues?: RecommendedCue[]
  expected_effect?: string
  raw_diagnosis?: string  // fallback when JSON parse fails
}

/** One recommended coaching cue extracted from diagnosis. */
export interface RecommendedCue {
  cue: string
  tier: number     // 1=external focus, 2=internal focus, 3=regression
  focus: string    // "external" | "internal" | "regression"
}

/** API chat response from POST /api/chat. */
export interface ChatResponse {
  reply: string
  diagnosis?: DiagnosisData | null
  recommended_cues?: RecommendedCue[] | null
}

/** One active cue being tracked for effectiveness. */
export interface ActiveCueTracking {
  error_name: string
  last_cue: string
  effective: boolean
  tried_cues: string[]
}

/** Cue effectiveness tracking data from the backend (Phase 4). */
export interface CueTrackingData {
  active_cues: ActiveCueTracking[]
}

/** Per-joint diagnostic entry from the diagnostic snapshot. */
export interface JointDiagEntry {
  joint_name: string
  current: number
  target: number
  deviation: number
  status: string
  std_dev: number
  stability: string
}

/** Angle trend from linear regression on recent frames. */
export interface AngleTrendData {
  direction: string
  slope: number
  recent_values: number[]
}

/** Co-occurring error pattern with biomechanical interpretation. */
export interface CooccurrenceEntry {
  errors: string[]
  interpretation: string
}

/** Full diagnostic snapshot computed per-frame (lightweight version of backend DiagnosticSnapshot). */
export interface DiagnosticSnapshotData {
  joint_deviations: JointDiagEntry[]
  angle_trend: AngleTrendData | null
  dimension_diagnosis: string
  error_cooccurrence: CooccurrenceEntry[]
}

export interface DetectionResult {
  detected: boolean
  keypoints?: number[][]
  score?: ScoreData
  phase?: string
  count?: number
  hold_time?: number
  errors?: ErrorData[]
  guidance?: GuidanceData
  debug?: DebugData
  heatmap?: HeatmapData
  cue_tracking?: CueTrackingData | null
  diagnostic_snapshot?: DiagnosticSnapshotData | null
}

export interface JointDeviation {
  key: string
  name: string
  user_avg: number
  standard_mid: number
  deviation: number
  deviation_ratio: number
  severity: 'good' | 'warning' | 'bad'
}

export interface HeatmapData {
  joints: JointDeviation[]
}

export type TrainingState = 'idle' | 'running' | 'paused'

/** Context snapshot sent to backend /api/chat as pose_context.
 *  All fields optional — the backend provides defaults for missing keys. */
export interface PoseContext {
  exercise_name: string
  score?: ScoreData
  phase?: string
  rep_count?: number
  hold_time?: number
  errors?: ErrorData[]
  best_score?: number
  recent_scores?: number[]
  chat_mode?: string
}

/** Specific trigger reason for proactive coach messages. */
export type CoachTriggerType =
  | 'severe_error'
  | 'score_drop'
  | 'personal_best'
  | 'milestone'
  | 'good_streak'
  | 'proactive'

/** Human-readable labels and icons for each trigger type. */
export const COACH_TRIGGER_META: Record<CoachTriggerType, { label: string; icon: string; color: string }> = {
  severe_error:  { label: '检测到动作风险', icon: '🔴', color: 'text-red-400' },
  score_drop:    { label: '动作质量下降',   icon: '📉', color: 'text-amber-400' },
  personal_best: { label: '突破个人记录',   icon: '🏆', color: 'text-yellow-400' },
  milestone:     { label: '达到里程碑',     icon: '🎯', color: 'text-emerald-400' },
  good_streak:   { label: '连续标准动作',   icon: '⭐', color: 'text-blue-400' },
  proactive:     { label: '教练提示',       icon: '⚡', color: 'text-flame/60' },
}

/** Proactive coaching message pushed from backend via WebSocket. */
export interface CoachMessage {
  type: 'coach'
  text: string
  trigger: CoachTriggerType
}

/** Training session record from backend history API. */
export interface SessionRecord {
  session_id: string
  exercise: string
  start_time: string
  duration_seconds: number
  total_reps: number
  best_score: number
  avg_score: number
  errors: Record<string, number>
}

/** User profile for plan generation. */
export interface UserProfile {
  name: string
  age: number
  weight_kg: number
  height_cm: number
  fitness_level: string
  goal: string
  equipment: string
  injury_history?: string
  liked_exercises?: string[]
  disliked_exercises?: string[]
  training_days_per_week?: number
  pain_points?: PainPoint[]
  workout_history?: WorkoutRecord[]
}

/** One completed workout record saved to user profile. */
export interface WorkoutRecord {
  date: string
  exercise: string
  total_reps: number
  best_score: number
  avg_score: number
  duration: string
  errors: ErrorSummary[]
}

/** Recurring pain point tracked across sessions. */
export interface PainPoint {
  error_name: string
  count: number
  last_seen: string
  suggestion: string
}

/** One step in an AI-generated workout plan. */
export interface PlanStep {
  exercise: string
  reps: number
  sets: number
  rest_seconds: number
  tempo?: string
  notes?: string
  duration_seconds?: number
}

/** A block of exercises in an AI plan. */
export interface PlanBlock {
  name: string
  rounds: number
  exercises: PlanStep[]
}

/** AI-generated workout plan. */
export interface AIPlan {
  plan_name: string
  plan_type: string
  total_duration_minutes: number
  warmup: PlanStep[]
  blocks: PlanBlock[]
  cooldown: PlanStep[]
}

/** One exercise in a daily plan. */
export interface ExercisePlan {
  name: string
  sets: number
  reps: number
  rest_seconds: number
  notes: string
}

/** One day in a weekly plan. */
export interface DailyPlan {
  day: string
  focus: string
  exercises: ExercisePlan[]
}

/** Full weekly workout plan. */
export interface WeeklyPlan {
  user_name: string
  goal: string
  level: string
  week_start: string
  days: DailyPlan[]
}

/** Error summary entry for training summary panel. */
export interface ErrorSummary {
  name: string
  count: number
  severity: number
  suggestion: string
}

/** A captured key frame (error onset or highlight moment). */
export interface KeyFrame {
  type: 'error' | 'highlight'
  label: string
  image: string   // base64 JPEG
  timestamp: string
}

/** Data for the post-set training summary panel. */
export interface SummaryData {
  exercise: string
  totalReps: number
  targetReps: number
  bestScore: number
  avgScore: number
  duration: string
  errors: ErrorSummary[]
  finalScore: ScoreData
  frames?: KeyFrame[]
}
