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
}

export type TrainingState = 'idle' | 'running' | 'paused'
