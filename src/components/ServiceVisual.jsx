// Mini UI illustrations for each service card (pure HTML/CSS/SVG)
export default function ServiceVisual({ type }) {
  switch (type) {
    case 'chat':
      return (
        <div className="viz viz--chat">
          <div className="viz__bar"><i /><i /><i /><span>Devliqly Assistant · online</span></div>
          <div className="bubble bubble--in" data-par="1">Do you deliver to Pune?</div>
          <div className="bubble bubble--out" data-par="2">Yes! Delivery to Pune takes 2–3 days and is free above ₹999. Want me to check a pincode?</div>
          <div className="bubble bubble--in" data-par="1.5">411001</div>
          <div className="bubble bubble--out typing" data-par="2.5"><i /><i /><i /></div>
        </div>
      )
    case 'support':
      return (
        <div className="viz viz--support">
          {[
            ['#4821', 'Where is my order?', 'Resolved', 'ok'],
            ['#4822', 'Refund for damaged item', 'Resolved', 'ok'],
            ['#4823', 'Change billing address', 'Resolved', 'ok'],
            ['#4824', 'Enterprise contract query', 'Handed to human', 'hand'],
          ].map(([id, t, s, k], i) => (
            <div className="ticket" key={id} data-par={1 + i * 0.6}>
              <span className="ticket__id">{id}</span>
              <span className="ticket__t">{t}</span>
              <span className={`ticket__s ticket__s--${k}`}>{s}</span>
            </div>
          ))}
        </div>
      )
    case 'calls':
      return (
        <div className="viz viz--calls">
          <div className="dial" data-par="1">
            <div className="dial__ring" /><div className="dial__ring dial__ring--2" />
            <svg viewBox="0 0 24 24" width="34" height="34" aria-hidden="true"><path fill="currentColor" d="M6.6 10.8a15.1 15.1 0 006.6 6.6l2.2-2.2a1 1 0 011-.25 11.4 11.4 0 003.6.6 1 1 0 011 1V20a1 1 0 01-1 1A17 17 0 013 4a1 1 0 011-1h3.5a1 1 0 011 1c0 1.25.2 2.45.6 3.6a1 1 0 01-.25 1z"/></svg>
          </div>
          <div className="calllog">
            {[
              ['in', '+91 98•• ••210', 'Booked visit', '1:42'],
              ['out', '+91 99•• ••871', 'Lead qualified', '2:05'],
              ['out', '+91 70•• ••334', 'Payment reminder', '0:58'],
              ['in', '+91 88•• ••902', 'Order status', '0:44'],
            ].map(([d, n, r, t], i) => (
              <div className="calllog__row" key={n} data-par={1 + i * 0.5}>
                <span className={`calllog__dir calllog__dir--${d}`}>{d === 'in' ? '↙' : '↗'}</span>
                <span className="calllog__n">{n}</span>
                <span className="calllog__r">{r}</span>
                <span className="calllog__t">{t}</span>
              </div>
            ))}
          </div>
        </div>
      )
    case 'voice':
      return (
        <div className="viz viz--voice">
          <div className="vwave" data-par="1.5">
            {Array.from({ length: 28 }).map((_, i) => <i key={i} style={{ '--i': i }} />)}
          </div>
          <div className="vmeta" data-par="2.5">
            <span className="vmeta__live"><i /> Live</span>
            <span>Latency 480ms</span>
            <span>Voice: “Aanya”</span>
          </div>
        </div>
      )
    case 'workflow':
      return (
        <div className="viz viz--flow">
          <svg className="flow__lines" viewBox="0 0 400 260" preserveAspectRatio="none" aria-hidden="true">
            <path d="M80 130 C 140 130, 140 130, 200 130" />
            <path d="M200 130 C 260 130, 260 50, 320 50" />
            <path d="M200 130 C 260 130, 260 130, 320 130" />
            <path d="M200 130 C 260 130, 260 210, 320 210" />
          </svg>
          <div className="node node--trigger" data-par="1">✉ New email</div>
          <div className="node node--agent" data-par="2"><b>AI Agent</b><small>reads · decides · acts</small></div>
          <div className="node node--o1" data-par="1.2">CRM updated</div>
          <div className="node node--o2" data-par="1.8">Invoice drafted</div>
          <div className="node node--o3" data-par="2.4">Slack alert</div>
        </div>
      )
    default:
      return null
  }
}
