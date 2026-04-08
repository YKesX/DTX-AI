import { useEffect, useState } from 'react';

const ACTIONS = [
  { key: 'acknowledge', label: 'Acknowledge' },
  { key: 'assign', label: 'Assign' },
  { key: 'escalate', label: 'Escalate' },
  { key: 'resolve', label: 'Resolve' },
];

export default function OperatorActionBar({
  event,
  disabled = false,
  loading = false,
  onSubmitAction,
}) {
  const [assignee, setAssignee] = useState(event?.assigned_to ?? '');
  const [note, setNote] = useState('');

  useEffect(() => {
    setAssignee(event?.assigned_to ?? '');
  }, [event?.assigned_to, event?.event_id]);

  const handleSubmit = async (actionType) => {
    if (!event?.event_id || !onSubmitAction) return;
    await onSubmitAction(actionType, {
      assignee,
      note,
    });
    if (actionType !== 'assign') setAssignee('');
    setNote('');
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
        <label className="space-y-1">
          <span className="text-[11px] uppercase tracking-wider text-gray-500">Assignee</span>
          <input
            type="text"
            value={assignee}
            onChange={(e) => setAssignee(e.target.value)}
            placeholder="Maintenance team / operator"
            disabled={disabled || loading}
            className="control-input w-full rounded-xl px-3 py-2 text-sm"
          />
        </label>

        <label className="space-y-1">
          <span className="text-[11px] uppercase tracking-wider text-gray-500">Note</span>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Short operator note"
            disabled={disabled || loading}
            className="control-input w-full rounded-xl px-3 py-2 text-sm"
          />
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((action) => (
          <button
            key={action.key}
            type="button"
            onClick={() => handleSubmit(action.key)}
            disabled={disabled || loading || (action.key === 'assign' && !assignee.trim())}
            className={`rounded-xl border px-3 py-2 text-sm transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
              action.key === 'assign'
                ? 'border-emerald-300/35 bg-emerald-300/10 text-emerald-100 hover:bg-emerald-300/16'
                : action.key === 'resolve'
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100 hover:bg-emerald-500/16'
                : action.key === 'escalate'
                ? 'border-blue-400/32 bg-blue-400/10 text-blue-100 hover:bg-blue-400/16'
                : 'border-[rgba(92,117,142,0.28)] bg-[rgba(17,24,32,0.84)] text-gray-100 hover:bg-[rgba(34,58,67,0.85)]'
            }`}
          >
            {loading ? 'Saving...' : action.label}
          </button>
        ))}
      </div>
    </div>
  );
}
