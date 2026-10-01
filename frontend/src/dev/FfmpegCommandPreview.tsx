// Dev-only helper: shows the FFmpeg command the chosen settings would produce.
// Rendered behind `import.meta.env.DEV`, so it is stripped from production builds.
// To remove it, delete this folder and its one usage in UploadPage.tsx.
//
// The key -> FFmpeg argument mapping below is only for display. The real
// mapping (and whitelist) must live in the backend worker.

import { useState } from 'react'
import type { TranscodeSettings } from '../config/transcodeOptions.ts'

const RESOLUTION_HEIGHTS: Record<TranscodeSettings['resolution'], string> = {
  '1080p': '1080',
  '720p': '720',
  '480p': '480',
}

const VIDEO_ENCODERS: Record<TranscodeSettings['videoCodec'], string> = {
  h264: 'libx264',
}

const AUDIO_ENCODERS: Record<TranscodeSettings['audioCodec'], string> = {
  mp3: 'libmp3lame',
}

// Each inner array is one flag and its value, printed on its own line.
function buildArgGroups(settings: TranscodeSettings, inputName: string) {
  const filters = [`scale=-2:${RESOLUTION_HEIGHTS[settings.resolution]}`]
  if (settings.brightness !== '0') {
    filters.push(`eq=brightness=${settings.brightness}`)
  }

  const groups: string[][] = [
    ['-i', inputName],
    ['-vf', filters.join(',')],
  ]
  if (settings.frameRate !== 'original') {
    groups.push(['-r', settings.frameRate])
  }
  groups.push(
    ['-c:v', VIDEO_ENCODERS[settings.videoCodec]],
    ['-preset', settings.encodingSpeed],
    ['-crf', settings.quality],
    ['-c:a', AUDIO_ENCODERS[settings.audioCodec]],
    [`output_${settings.resolution}.mp4`],
  )
  return groups
}

// Quote for a POSIX shell so the printed command can be pasted into a terminal.
function shellQuote(arg: string) {
  if (/^[\w./:=,+-]+$/.test(arg)) return arg
  return `'${arg.replace(/'/g, `'\\''`)}'`
}

type FfmpegCommandPreviewProps = {
  settings: TranscodeSettings
  fileName?: string
}

function FfmpegCommandPreview({ settings, fileName }: FfmpegCommandPreviewProps) {
  const [copied, setCopied] = useState(false)

  const [first, ...rest] = buildArgGroups(settings, fileName ?? 'input.mp4').map(
    (group) => group.map(shellQuote).join(' '),
  )
  const command = [`ffmpeg ${first}`, ...rest].join(' \\\n  ')

  function handleCopy() {
    navigator.clipboard
      .writeText(command)
      .then(() => setCopied(true))
      .catch(() => setCopied(false))
  }

  return (
    <aside className="dev-preview" aria-label="FFmpeg command preview">
      <h2 className="dev-preview__title">FFmpeg command (dev only)</h2>
      <pre className="dev-preview__command">
        <code>{command}</code>
      </pre>
      <button className="dev-preview__copy" type="button" onClick={handleCopy}>
        {copied ? 'Copied' : 'Copy command'}
      </button>
    </aside>
  )
}

export default FfmpegCommandPreview
