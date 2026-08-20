// Decision identity is always colour + text, never colour alone.
const ICONS = { ALLOW: '✓', STEP_UP: '!', REVIEW: '⌕', BLOCK: '✕' }

export default function DecisionChip({ decision }) {
  return (
    <span className={`chip chip-${decision}`}>
      <span aria-hidden="true">{ICONS[decision]}</span>
      {decision.replace('_', ' ')}
    </span>
  )
}
