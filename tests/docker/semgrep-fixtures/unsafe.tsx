export function UnsafeView({ value }: { value: string }) {
  const node = document.createElement('div');
  node.innerHTML = value;
  return <div>{eval(value)}</div>;
}
