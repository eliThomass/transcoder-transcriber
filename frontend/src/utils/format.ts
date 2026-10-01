const HOUR_MS = 60 * 60 * 1000
const DAY_MS = 24 * HOUR_MS

export function formatFileSize(bytes: number) {
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

const dateFormat = new Intl.DateTimeFormat('en', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
})

export function formatDate(isoDate: string) {
  return dateFormat.format(new Date(isoDate))
}

const relativeFormat = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

// "Expires in 3 hours", "Expires tomorrow", "Expires in 6 days"
export function formatExpiry(isoDate: string) {
  const remaining = new Date(isoDate).getTime() - Date.now()
  if (remaining <= 0) return 'Expired'
  const hours = Math.ceil(remaining / HOUR_MS)
  if (hours < 24) {
    return `Expires ${relativeFormat.format(hours, 'hour')}`
  }
  return `Expires ${relativeFormat.format(Math.round(remaining / DAY_MS), 'day')}`
}
