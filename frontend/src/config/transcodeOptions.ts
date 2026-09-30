// Option values are short keys, not raw FFmpeg arguments. The API must map
// each key to its FFmpeg flags from its own whitelist (e.g. 'h264' -> '-c:v libx264')
// so user input never reaches the FFmpeg command line directly.

export type Option<T extends string> = {
  readonly value: T
  readonly label: string
}

export const RESOLUTIONS = [
  { value: '1080p', label: '1080p (Full HD)' },
  { value: '720p', label: '720p (HD)' },
  { value: '480p', label: '480p (SD)' },
] as const satisfies readonly Option<string>[]

export const FRAME_RATES = [
  { value: 'original', label: 'Keep original' },
  { value: '24', label: '24 fps' },
  { value: '30', label: '30 fps' },
  { value: '60', label: '60 fps' },
] as const satisfies readonly Option<string>[]

export const VIDEO_CODECS = [
  { value: 'h264', label: 'H.264 (most compatible)' },
  { value: 'h265', label: 'H.265 / HEVC (smaller files, slower)' },
] as const satisfies readonly Option<string>[]

// FFmpeg -preset: slower presets compress better but take more compute.
export const ENCODING_SPEEDS = [
  { value: 'ultrafast', label: 'Ultrafast (largest file)' },
  { value: 'superfast', label: 'Superfast' },
  { value: 'veryfast', label: 'Very fast' },
  { value: 'faster', label: 'Faster' },
  { value: 'fast', label: 'Fast' },
  { value: 'medium', label: 'Medium (default)' },
  { value: 'slow', label: 'Slow' },
  { value: 'slower', label: 'Slower' },
  { value: 'veryslow', label: 'Very slow (smallest file)' },
] as const satisfies readonly Option<string>[]

// FFmpeg -crf: lower is higher quality and a larger file.
export const QUALITY_LEVELS = [
  { value: '18', label: 'Highest (CRF 18)' },
  { value: '20', label: 'High (CRF 20)' },
  { value: '23', label: 'Standard (CRF 23)' },
  { value: '26', label: 'Low (CRF 26)' },
  { value: '28', label: 'Lowest (CRF 28)' },
] as const satisfies readonly Option<string>[]

// FFmpeg -vf "eq=brightness=N"
export const BRIGHTNESS_LEVELS = [
  { value: '-0.2', label: 'Much darker' },
  { value: '-0.1', label: 'Darker' },
  { value: '0', label: 'Unchanged' },
  { value: '0.1', label: 'Brighter' },
  { value: '0.2', label: 'Much brighter' },
] as const satisfies readonly Option<string>[]

export const AUDIO_CODECS = [
  { value: 'aac', label: 'AAC (standard for MP4)' },
  { value: 'mp3', label: 'MP3' },
  { value: 'opus', label: 'Opus (efficient, less compatible)' },
] as const satisfies readonly Option<string>[]

export const AUDIO_BITRATES = [
  { value: '96k', label: '96 kbps' },
  { value: '128k', label: '128 kbps' },
  { value: '192k', label: '192 kbps' },
  { value: '256k', label: '256 kbps' },
] as const satisfies readonly Option<string>[]

type ValueOf<T extends readonly Option<string>[]> = T[number]['value']

export type TranscodeSettings = {
  resolution: ValueOf<typeof RESOLUTIONS>
  frameRate: ValueOf<typeof FRAME_RATES>
  videoCodec: ValueOf<typeof VIDEO_CODECS>
  encodingSpeed: ValueOf<typeof ENCODING_SPEEDS>
  quality: ValueOf<typeof QUALITY_LEVELS>
  brightness: ValueOf<typeof BRIGHTNESS_LEVELS>
  audioCodec: ValueOf<typeof AUDIO_CODECS>
  audioBitrate: ValueOf<typeof AUDIO_BITRATES>
}

export const QUALITY_PRESETS = {
  low: {
    resolution: '480p',
    frameRate: '30',
    videoCodec: 'h264',
    encodingSpeed: 'veryfast',
    quality: '28',
    brightness: '0',
    audioCodec: 'aac',
    audioBitrate: '96k',
  },
  medium: {
    resolution: '720p',
    frameRate: '30',
    videoCodec: 'h264',
    encodingSpeed: 'medium',
    quality: '23',
    brightness: '0',
    audioCodec: 'aac',
    audioBitrate: '128k',
  },
  high: {
    resolution: '1080p',
    frameRate: '30',
    videoCodec: 'h264',
    encodingSpeed: 'slow',
    quality: '20',
    brightness: '0',
    audioCodec: 'aac',
    audioBitrate: '192k',
  },
} as const satisfies Record<string, TranscodeSettings>

export type PresetChoice = keyof typeof QUALITY_PRESETS | 'custom'

export const PRESET_CHOICES = [
  { value: 'low', label: 'Low (480p, smallest file)' },
  { value: 'medium', label: 'Medium (720p, balanced)' },
  { value: 'high', label: 'High (1080p, best quality)' },
  { value: 'custom', label: 'Custom' },
] as const satisfies readonly Option<PresetChoice>[]

export const DEFAULT_PRESET = 'medium' satisfies PresetChoice
