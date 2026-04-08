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
            className="w-full rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
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
            className="w-full rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
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
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Saving...' : action.label}
          </button>
        ))}
      </div>
    </div>
  );
}
