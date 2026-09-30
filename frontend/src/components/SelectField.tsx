import type { Option } from '../config/transcodeOptions.ts'

type SelectFieldProps<T extends string> = {
  id: string
  label: string
  value: T
  options: readonly Option<T>[]
  onChange: (value: T) => void
  hint?: string
}

function SelectField<T extends string>({
  id,
  label,
  value,
  options,
  onChange,
  hint,
}: SelectFieldProps<T>) {
  const hintId = hint ? `${id}-hint` : undefined

  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <select
        className="field__select"
        id={id}
        value={value}
        aria-describedby={hintId}
        // Safe cast: the only selectable values are the ones in `options`.
        onChange={(event) => onChange(event.target.value as T)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint && (
        <p className="field__hint" id={hintId}>
          {hint}
        </p>
      )}
    </div>
  )
}

export default SelectField
