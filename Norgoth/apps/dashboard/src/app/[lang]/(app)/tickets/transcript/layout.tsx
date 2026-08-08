/**
 * Minimal chrome for member-facing ticket transcripts.
 * Parent AppShell also skips CCC nav for this path; this layout
 * keeps the route self-documenting and future-proof.
 */
export default function TranscriptLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="norgoth-transcript-layout">{children}</div>;
}
