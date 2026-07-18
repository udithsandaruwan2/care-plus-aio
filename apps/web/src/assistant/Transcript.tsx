type Props = {
  transcript: string;
  interim: string;
};

/** Live transcript — finalized text plus in-flight interim words. */
export function Transcript({ transcript, interim }: Props) {
  if (!transcript && !interim) {
    return null;
  }
  return (
    <p className="mt-3 max-w-md text-center text-sm leading-relaxed text-mist">
      {transcript}{' '}
      {interim && <span className="text-muted italic">{interim}</span>}
    </p>
  );
}
