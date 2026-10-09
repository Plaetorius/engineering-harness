# Pattern examples

Small, deliberately generic sketches (a project-board domain) for the decisions in the skill. Adapt names and imports to the repository; verify against the installed React and Next.js versions.

## Composition with children and slots

```tsx
export function Panel({ title, actions, children }: {
  title: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby="panel-title" className="panel">
      <header className="panel-head">
        <h2 id="panel-title">{title}</h2>
        {actions}
      </header>
      {children}
    </section>
  );
}
```

(Use `useId` for the heading id when several panels can share a page.)

## A family of parts sharing scoped state

```tsx
const TabsCtx = createContext<{ value: string; set: (v: string) => void } | null>(null);

function useTabs() {
  const ctx = useContext(TabsCtx);
  if (!ctx) throw new Error("Tab parts must be rendered inside <Tabs>");
  return ctx;
}

export function Tabs({ initial, children }: { initial: string; children: React.ReactNode }) {
  const [value, set] = useState(initial);
  return <TabsCtx value={{ value, set }}>{children}</TabsCtx>;
}

export function Tab({ id, children }: { id: string; children: React.ReactNode }) {
  const { value, set } = useTabs();
  return (
    <button role="tab" aria-selected={value === id} onClick={() => set(id)}>
      {children}
    </button>
  );
}
```

(Real tab lists also need roving focus and arrow-key handling; prefer the project's tested primitive.)

## Children as a function when markup varies

```tsx
export function WhenLoaded<T>({ query, children }: {
  query: { data?: T; error?: Error; pending: boolean; refetch: () => void };
  children: (data: T) => React.ReactNode;
}) {
  if (query.pending) return <Skeleton />;
  if (query.error) return <ErrorNotice onRetry={query.refetch} />;
  return query.data ? children(query.data) : <EmptyNotice />;
}
```

## Debounced value for search-as-you-type

```ts
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setSettled(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return settled;
}
```

Fire the request from the settled value, ignore results that arrive for an older query, and show that a search is running.

## Reducer plus scoped provider (split state and dispatch)

```tsx
type Action = { type: "select"; id: string } | { type: "filter"; text: string } | { type: "clear" };
type State = { selected: string | null; filter: string };

function reduce(state: State, action: Action): State {
  switch (action.type) {
    case "select": return { ...state, selected: action.id };
    case "filter": return { ...state, filter: action.text };
    case "clear":  return { selected: null, filter: "" };
  }
}

const StateCtx = createContext<State | null>(null);
const DispatchCtx = createContext<React.Dispatch<Action> | null>(null);

export function BoardProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reduce, { selected: null, filter: "" });
  return (
    <DispatchCtx value={dispatch}>
      <StateCtx value={state}>{children}</StateCtx>
    </DispatchCtx>
  );
}
```

## Lazy loading a heavy widget

```tsx
const Chart = dynamic(() => import("./chart"), { loading: () => <ChartSkeleton /> });
```

Give the placeholder the same dimensions as the final chart so the page does not shift when it arrives.

## Virtualizing a long list

Use a virtualization library when hundreds of rows render together. Give the scroll container a fixed height, estimate row height, render a few rows of overscan, and keep each row's key stable. Check keyboard navigation and find-in-page still behave acceptably before adopting it.

## Form with accessible errors

```tsx
function Field({ id, label, error, ...input }: FieldProps) {
  const errId = `${id}-error`;
  return (
    <div>
      <label htmlFor={id}>{label}</label>
      <input id={id} aria-invalid={!!error} aria-describedby={error ? errId : undefined} {...input} />
      {error ? <p id={errId} role="alert">{error}</p> : null}
    </div>
  );
}
```

On a failed submit, keep the values, then focus the first invalid field (or a linked error summary when several fields failed).

## Error boundary around an independent widget

```tsx
export class WidgetBoundary extends React.Component<
  { children: React.ReactNode; fallback: (reset: () => void) => React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error) { reportError(error); }
  render() {
    return this.state.failed
      ? this.props.fallback(() => this.setState({ failed: false }))
      : this.props.children;
  }
}
```

The fallback says what part failed and offers a retry; it does not show the exception text.

## Enter/exit animation

Prefer CSS (`@starting-style`, transitions on opacity and transform) for simple reveals. Use an animation library for lists whose items mount and unmount, keyed by a stable id, with short durations (about 150 to 300 ms), exits shorter than entrances, and `prefers-reduced-motion` honored.

## Minimum for a custom listbox or menu

Keep the active index in state. ArrowDown and ArrowUp move it within bounds, Home and End jump, Enter selects, Escape closes and returns focus to the trigger. Expose `role`, `aria-expanded`, `aria-controls` and `aria-activedescendant` consistently. Test with a screen reader before shipping.

## Dialog focus handling

On open, remember the previously focused element and move focus inside the dialog. Trap Tab within it, close on Escape, and restore focus to the remembered element on close. The native `<dialog>` element with `showModal()` provides most of this; prefer it or the project's dialog primitive.
