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
}

export interface GuidanceData {
  type: string
  text: string
  priority: number
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

/** Proactive coaching message pushed from backend via WebSocket. */
export interface CoachMessage {
  type: 'coach'
  text: string
  trigger: string
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
}
