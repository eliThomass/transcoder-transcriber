import { useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import SelectField from '../components/SelectField.tsx'
import {
  AUDIO_CODECS,
  BRIGHTNESS_LEVELS,
  DEFAULT_PRESET,
  ENCODING_SPEEDS,
  FRAME_RATES,
  PRESET_CHOICES,
  QUALITY_LEVELS,
  QUALITY_PRESETS,
  RESOLUTIONS,
  VIDEO_CODECS,
} from '../config/transcodeOptions.ts'
import type { PresetChoice, TranscodeSettings } from '../config/transcodeOptions.ts'
import FfmpegCommandPreview from '../dev/FfmpegCommandPreview.tsx'

// Client-side check for a friendlier error only. The server must still
// validate the upload itself (e.g. with ffprobe) since this is easy to bypass.
function isMp4(file: File) {
  const hasMp4Extension = file.name.toLowerCase().endsWith('.mp4')
  const hasMp4Type = file.type === '' || file.type === 'video/mp4'
  return hasMp4Extension && hasMp4Type
}

function formatFileSize(bytes: number) {
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [presetChoice, setPresetChoice] = useState<PresetChoice>(DEFAULT_PRESET)
  const [settings, setSettings] = useState<TranscodeSettings>(
    QUALITY_PRESETS[DEFAULT_PRESET],
  )
  const [transcribe, setTranscribe] = useState(true)
  const [status, setStatus] = useState<string | null>(null)

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null
    setStatus(null)

    if (selected && !isMp4(selected)) {
      setFile(null)
      setFileError('Only MP4 files are supported right now.')
      event.target.value = ''
      return
    }

    setFile(selected)
    setFileError(null)
  }

  function handlePresetChange(choice: PresetChoice) {
    setPresetChoice(choice)
    if (choice !== 'custom') {
      setSettings(QUALITY_PRESETS[choice])
    }
  }

  // Editing any individual option switches the preset to "Custom".
  function updateSetting<K extends keyof TranscodeSettings>(
    key: K,
    value: TranscodeSettings[K],
  ) {
    setSettings((previous) => ({ ...previous, [key]: value }))
    setPresetChoice('custom')
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) {
      setFileError('Choose an MP4 file to upload.')
      return
    }

    // TODO: request a presigned upload URL from the API, PUT the file to S3,
    // then create the job with { settings, transcribe }.
    setStatus('Uploading is not connected to the backend yet.')
  }

  return (
    <main className="upload-page">
      <header className="upload-page__header">
        <h1 className="upload-page__title">Transcode &amp; Transcribe</h1>
        <p className="upload-page__description">
          Upload an MP4 video, choose your output settings, and optionally
          generate a transcript.
        </p>
      </header>

      <form className="upload-form" onSubmit={handleSubmit}>
        <fieldset className="upload-form__section upload-form__section--file">
          <legend className="upload-form__legend">Video file</legend>
          <div className="field">
            <label className="field__label" htmlFor="video-file">
              MP4 file
            </label>
            <input
              className="field__file"
              id="video-file"
              type="file"
              accept="video/mp4,.mp4"
              aria-describedby={fileError ? 'video-file-error' : undefined}
              aria-invalid={fileError ? true : undefined}
              onChange={handleFileChange}
            />
            {file && (
              <p className="field__file-info">
                <span className="field__file-name">{file.name}</span>{' '}
                <span className="field__file-size">
                  ({formatFileSize(file.size)})
                </span>
              </p>
            )}
            {fileError && (
              <p className="field__error" id="video-file-error" role="alert">
                {fileError}
              </p>
            )}
          </div>
        </fieldset>

        <fieldset className="upload-form__section upload-form__section--preset">
          <legend className="upload-form__legend">Preset</legend>
          <SelectField
            id="preset"
            label="Quality preset"
            value={presetChoice}
            options={PRESET_CHOICES}
            onChange={handlePresetChange}
            hint="Choosing a preset fills in the settings below. Changing any setting switches to Custom."
          />
        </fieldset>

        <fieldset className="upload-form__section upload-form__section--video">
          <legend className="upload-form__legend">Video settings</legend>
          <SelectField
            id="resolution"
            label="Resolution"
            value={settings.resolution}
            options={RESOLUTIONS}
            onChange={(value) => updateSetting('resolution', value)}
          />
          <SelectField
            id="frame-rate"
            label="Frame rate"
            value={settings.frameRate}
            options={FRAME_RATES}
            onChange={(value) => updateSetting('frameRate', value)}
          />
          <SelectField
            id="video-codec"
            label="Video codec"
            value={settings.videoCodec}
            options={VIDEO_CODECS}
            onChange={(value) => updateSetting('videoCodec', value)}
          />
          <SelectField
            id="encoding-speed"
            label="Encoding speed"
            value={settings.encodingSpeed}
            options={ENCODING_SPEEDS}
            onChange={(value) => updateSetting('encodingSpeed', value)}
            hint="Slower encoding produces smaller files at the same quality."
          />
          <SelectField
            id="quality"
            label="Quality"
            value={settings.quality}
            options={QUALITY_LEVELS}
            onChange={(value) => updateSetting('quality', value)}
            hint="Higher quality produces larger files."
          />
          <SelectField
            id="brightness"
            label="Brightness"
            value={settings.brightness}
            options={BRIGHTNESS_LEVELS}
            onChange={(value) => updateSetting('brightness', value)}
          />
        </fieldset>

        <fieldset className="upload-form__section upload-form__section--audio">
          <legend className="upload-form__legend">Audio settings</legend>
          <SelectField
            id="audio-codec"
            label="Audio codec"
            value={settings.audioCodec}
            options={AUDIO_CODECS}
            onChange={(value) => updateSetting('audioCodec', value)}
          />
        </fieldset>

        <fieldset className="upload-form__section upload-form__section--transcription">
          <legend className="upload-form__legend">Transcription</legend>
          <div className="field field--checkbox">
            <input
              className="field__checkbox"
              id="transcribe"
              type="checkbox"
              checked={transcribe}
              onChange={(event) => setTranscribe(event.target.checked)}
            />
            <label className="field__label" htmlFor="transcribe">
              Generate a transcript
            </label>
          </div>
        </fieldset>

        <div className="upload-form__actions">
          <button className="upload-form__submit" type="submit" disabled={!file}>
            Upload and process
          </button>
        </div>

        {status && (
          <p className="upload-form__status" role="status">
            {status}
          </p>
        )}
      </form>

      {import.meta.env.DEV && (
        <FfmpegCommandPreview settings={settings} fileName={file?.name} />
      )}
    </main>
  )
}

export default UploadPage
