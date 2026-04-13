export default function Card({ children, className = '' }) {
  return (
    <div
      className={`control-panel rounded-2xl ${className}`}
    >
      {children}
    </div>
  );
}
