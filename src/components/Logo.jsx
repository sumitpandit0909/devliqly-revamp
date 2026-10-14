export default function Logo() {
  return (
    <span className="logo">
      <svg viewBox="0 0 64 64" width="30" height="30" aria-hidden="true">
        <path d="M18 14h14a18 18 0 0 1 0 36H18z" fill="none" stroke="currentColor" strokeWidth="7" />
        <circle cx="32" cy="32" r="5" fill="var(--accent)" />
      </svg>
      <span className="logo__text">DEVLIQLY<i>.</i></span>
    </span>
  )
}
