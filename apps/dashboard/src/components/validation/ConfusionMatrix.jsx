import Card from '../ui/Card';

function buildMatrix(confusionCounts = {}) {
  const pairs = Object.entries(confusionCounts).map(([key, value]) => {
    const [actual, predicted] = key.split('->');
    return { actual, predicted, value };
  });
  const labels = Array.from(
    new Set(
      pairs.flatMap((pair) => [pair.actual, pair.predicted]).filter(Boolean)
    )
  );
  const index = new Map(labels.map((label, i) => [label, i]));
  const matrix = labels.map(() => labels.map(() => 0));

  pairs.forEach((pair) => {
    matrix[index.get(pair.actual)][index.get(pair.predicted)] = pair.value;
  });

  return { labels, matrix };
}

export default function ConfusionMatrix({ metrics }) {
  const { labels, matrix } = buildMatrix(metrics?.confusion_counts ?? {});

  return (
    <Card className="p-5">
      <div className="mb-4">
        <h2 className="section-title">
          Confusion Matrix
        </h2>
        <p className="mt-1 text-sm text-muted">
          Ground-truth and prediction matches during replay
        </p>
      </div>

      {labels.length === 0 ? (
        <div className="flex h-48 items-center justify-center text-sm text-dim">
          Not enough replay data to build the matrix.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-line text-xs uppercase tracking-[0.18em] text-dim">
                <th className="px-3 py-2 text-left">Actual \ Pred</th>
                {labels.map((label) => (
                  <th key={label} className="px-3 py-2 text-left">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {labels.map((actual, rowIndex) => (
                <tr key={actual} className="border-b border-line">
                  <td className="px-3 py-2 font-medium text-ink">{actual}</td>
                  {labels.map((predicted, colIndex) => {
                    const value = matrix[rowIndex][colIndex];
                    const isDiagonal = rowIndex === colIndex;
                    return (
                      <td
                        key={`${actual}-${predicted}`}
                        className={`px-3 py-2 ${
                          isDiagonal ? 'text-emerald-800' : 'text-muted'
                        }`}
                      >
                        {value}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
