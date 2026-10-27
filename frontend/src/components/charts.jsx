// Two small single-series charts, plain HTML/CSS.
// One ink colour (the theme's text colour); every value is also printed as text,
// each mark has a hover/focus tooltip, and a hidden table backs every chart for screen readers.

// Ranked magnitude: horizontal bars, label left, value right (direct-labelled)
export function BarList({ items, label, valueLabel = 'faculty', empty = 'No data yet.' }) {
  if (!items.length) return <p className="muted small">{empty}</p>
  const max = Math.max(...items.map((i) => i.count))
  return (
    <figure className="chart">
      <ol className="bar-list" aria-hidden="true">
        {items.map((it, i) => (
          <li key={it.keyword} className="bar-row" style={{ '--i': i }}>
            <span className="bar-label">{it.keyword}</span>
            <span className="bar-track" tabIndex={0} data-tip={`${it.keyword}: ${it.count} ${valueLabel}`}>
              <span className="bar-fill" style={{ '--w': `${(it.count / max) * 100}%` }} />
            </span>
            <span className="bar-value">{it.count}</span>
          </li>
        ))}
      </ol>
      <table className="sr-only">
        <caption>{label}</caption>
        <thead><tr><th>Keyword</th><th>Count</th></tr></thead>
        <tbody>{items.map((it) => <tr key={it.keyword}><td>{it.keyword}</td><td>{it.count}</td></tr>)}</tbody>
      </table>
    </figure>
  )
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function monthName(ym, long = false) {
  const [y, m] = ym.split('-').map(Number)
  return long ? `${MONTHS[m - 1]} ${y}` : MONTHS[m - 1]
}

// Change over time: 12 columns on a shared baseline, one recessive guide line at the max
export function MonthColumns({ months, label }) {
  const max = Math.max(1, ...months.map((m) => m.count))
  const total = months.reduce((s, m) => s + m.count, 0)
  return (
    <figure className="chart">
      <div className="columns" aria-hidden="true">
        <span className="columns-guide" data-value={max} />
        {months.map((m, i) => (
          <div key={m.month} className="column" style={{ '--i': i }}>
            <span className="column-track" tabIndex={0} data-tip={`${monthName(m.month, true)}: ${m.count}`}>
              <span className="column-fill" style={{ '--h': `${(m.count / max) * 100}%` }} />
            </span>
            <span className="column-label">{monthName(m.month)}</span>
          </div>
        ))}
      </div>
      <figcaption className="muted small">{total} in the last 12 months</figcaption>
      <table className="sr-only">
        <caption>{label}</caption>
        <thead><tr><th>Month</th><th>Count</th></tr></thead>
        <tbody>{months.map((m) => <tr key={m.month}><td>{monthName(m.month, true)}</td><td>{m.count}</td></tr>)}</tbody>
      </table>
    </figure>
  )
}
