export default function Card({ children, className = '' }) {
  return (
    <div
      className={`bg-gray-800 border border-gray-700 rounded-xl shadow-lg ${className}`}
    >
      {children}
    </div>
  );
}
