export default function StatusBadge({ status }) {
  const map = {
    pending:    { label: 'Queued',        cls: 'tag-amber' },
    processing: { label: 'Processing',    cls: 'tag-amber' },
    ready:      { label: 'Ready',         cls: 'tag-sky'   },
    complete:   { label: 'Fully indexed', cls: 'tag-sky'   },
    failed:     { label: 'Failed',        cls: 'tag-coral' },
  }
  const { label, cls } = map[status] || { label: status, cls: 'tag-coral' }
  return <span className={`tag ${cls}`}>{label}</span>
}