// Grid and Solar asset-pack screens (spec §10, storyboard 2:18–2:28). Thin: same shell, checker
// findings and Asset agent narration; results from the static bundle or POST /api/asset/{pack}.
import { cn } from 'cn'
import { RotateCcw, SunMedium, TriangleAlert, UtilityPole } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { AgentDot, EmptyState, IllustrativeLabel, Num } from '@/components/Labels'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { useProjectData } from '@/data/useProjectData'
import { useWorldProject } from '@/data/useWorld'
import { describeKey, fillPlaceholders, fmtNum, fmtQty, fmtUsd } from '@/lib/format'
import type { AssetResult } from '@/lib/types'
import { useServices } from '@/services/services'
import { assetResultFrom, chosenOption, geometryShapes, miniSld, optionColumns, optionId, optionName, shapeBounds } from './assetResult'

function cell(key: string, v: unknown): string {
  if (typeof v !== 'number') return v === null || v === undefined ? '—' : String(v)
  const d = describeKey(key)
  return d.usd ? fmtUsd(v) : fmtNum(v)
}

function header(key: string): string {
  const d = describeKey(key)
  return d.unit ? `${d.label} (${d.unit})` : d.usd ? `${d.label} (USD)` : d.label
}

function GeometryView({ geometry }: { geometry: Record<string, unknown> }) {
  const s = geometryShapes(geometry)
  const b = shapeBounds(s)
  if (!b) return null
  const pad = Math.max(b[2] - b[0], b[3] - b[1]) * 0.05 || 1
  const [x0, y0, w, h] = [b[0] - pad, b[1] - pad, b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad]
  // y is north-up in engine coordinates; flip for SVG.
  const pt = ([x, y]: [number, number]) => `${x},${y0 + h - (y - y0)}`
  const stroke = Math.max(w, h) / 300
  return (
    <svg role="img" aria-label="Site geometry" viewBox={`${x0} ${y0} ${w} ${h}`} className="h-64 w-full rounded border bg-zinc-950">
      {s.polygons.map((p) => (
        <polygon key={p.id} points={p.points.map(pt).join(' ')} fill="rgba(45,212,191,0.08)" stroke="#2dd4bf" strokeWidth={stroke} />
      ))}
      {s.rects.map(({ id, r }) => (
        <rect key={id} x={r[0]} y={y0 + h - (r[3] - y0)} width={r[2] - r[0]} height={r[3] - r[1]} fill="#1e3a5f" stroke="#60a5fa" strokeWidth={stroke / 2} />
      ))}
      {s.lines.map((l) => (
        <polyline key={l.id} points={l.points.map(pt).join(' ')} fill="none" stroke="#fbbf24" strokeWidth={stroke * 1.5} />
      ))}
      {s.points.map((p) => (
        <g key={p.id}>
          <circle cx={p.p[0]} cy={y0 + h - (p.p[1] - y0)} r={stroke * 4} fill="#e4e4e7" />
          <text x={p.p[0]} y={y0 + h - (p.p[1] - y0) - stroke * 6} fontSize={stroke * 10} fill="#a1a1aa" textAnchor="middle">
            {p.id}
          </text>
        </g>
      ))}
    </svg>
  )
}

/** Solar-only: the engine's clear-sky specific yield (no weather data behind it — labelled as such). */
function SolarYield({ geometry }: { geometry: Record<string, unknown> }) {
  const v = geometry.clear_sky_kwh_per_kwp
  if (typeof v !== 'number') return null
  return (
    <p className="text-xs text-zinc-400">
      Specific yield <Num>{fmtNum(Math.round(v))} kWh/kWp</Num>{' '}
      <span className="text-zinc-500">· clear-sky (no weather data)</span>
    </p>
  )
}

export function AssetPackView({
  pack,
  result,
  onRerun,
  rerunning,
  narration,
}: {
  pack: 'grid' | 'solar'
  result: AssetResult
  onRerun: () => void
  rerunning: boolean
  narration: string | null
}) {
  const cols = optionColumns(result.options)
  const sld = miniSld(result)
  const chosen = chosenOption(result)
  return (
    <div className="flex flex-col gap-5">
      <section aria-label="Options" className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-400">
            {pack === 'grid' ? 'Conductor options' : 'String and layout options'}
          </h2>
          <Button size="xs" variant="outline" className="ml-auto" onClick={onRerun} disabled={rerunning}>
            <RotateCcw aria-hidden /> Re-run with the engine
          </Button>
        </div>
        <table className="w-full text-xs" aria-label="Asset options">
          <thead>
            <tr>
              <th className="border-b px-2 py-1 text-left text-zinc-400">Option</th>
              {cols.map((c) => (
                <th key={c} className="border-b px-2 py-1 text-left font-medium text-zinc-400">
                  {header(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.options.map((o) => {
              const rec = optionId(o) === chosen || optionName(o) === chosen
              return (
                <tr key={optionId(o)} className={cn(rec && 'bg-teal-500/10')}>
                  <td className="border-b border-zinc-800 px-2 py-1 text-zinc-100">
                    {optionName(o)}
                    {rec && <span className="ml-2 rounded border border-teal-400/60 px-1 text-[10px] text-teal-200">Recommended</span>}
                  </td>
                  {cols.map((c) => (
                    <td key={c} className="border-b border-zinc-800 px-2 py-1 font-mono tabular-nums">
                      {cell(c, o[c])}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
        {pack === 'solar' && <SolarYield geometry={result.geometry} />}
        {narration && (
          <p className="flex items-center gap-2 text-xs text-zinc-300">
            <AgentDot agent="asset" /> {narration}
          </p>
        )}
      </section>
      <section aria-label="Checks" className="flex flex-col gap-1">
        <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-400">Checker</h2>
        <ul className="flex flex-col gap-1 text-sm">
          {result.findings.map((f) => (
            <li key={f.id} className="flex flex-wrap items-center gap-2">
              <StatusBadge status={f.status} />
              <span className="font-mono text-zinc-200">
                {f.rule_id} · {f.element_id}
              </span>
              <span className="text-zinc-400">{f.title}</span>
              {typeof f.value === 'number' && (
                <span className="text-xs text-zinc-400">
                  <Num>{fmtQty(f.value, f.unit)}</Num> vs <Num>{fmtQty(f.limit ?? null, f.unit)}</Num>
                </span>
              )}
              {f.explanation && <span className="w-full pl-6 text-xs text-zinc-500">{fillPlaceholders(f.explanation, f)}</span>}
            </li>
          ))}
        </ul>
      </section>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <section aria-label="Geometry">
          <GeometryView geometry={result.geometry} />
        </section>
        {sld && (
          <section aria-label="Mini SLD" className="flex flex-col items-start gap-1 text-xs">
            {sld.nodes.map((n, i) => {
              const edge = sld.edges.find((e) => e.dst === n.id)
              return (
                <div key={n.id} className="flex flex-col items-start">
                  {i > 0 && (
                    <span className="ml-4 border-l border-zinc-600 py-1 pl-2 font-mono text-[10px] text-zinc-500">{edge?.label ?? ''}</span>
                  )}
                  <span className="rounded border bg-card px-2 py-1">
                    <span className="font-mono text-zinc-100">{n.id}</span> <span className="text-zinc-400">{n.label}</span>
                  </span>
                </div>
              )
            })}
          </section>
        )}
      </div>
      <IllustrativeLabel />
    </div>
  )
}

export function AssetPackPage({ pack, pid }: { pack: 'grid' | 'solar'; pid: string }) {
  const project = useWorldProject(pid)
  const data = useProjectData(pid, { project })
  const { api } = useServices()
  const [override, setOverride] = useState<AssetResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const Icon = pack === 'grid' ? UtilityPole : SunMedium
  const result = override ?? (data.bundle ? assetResultFrom(data.bundle) : null)
  const recorded = data.bundle
    ? [...data.bundle.events].reverse().find((e) => e.agent === 'asset' && e.kind === 'message')?.title ?? null
    : null
  const narration = result?.choice?.reason ?? recorded // WS2's Asset agent reason (digit-filtered server-side)

  const rerun = async () => {
    if (busy) return // the re-run button cannot double-submit
    setBusy(true)
    setError(null)
    try {
      setOverride(await api.asset(pack))
    } catch {
      setError('The engine is unreachable; showing the recorded result.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col gap-4 overflow-auto p-6">
      <header className="flex flex-wrap items-center gap-2">
        <Link to="/app" className="text-sm text-zinc-400 hover:text-zinc-100">
          Projects
        </Link>
        <span className="text-zinc-600">/</span>
        <Icon aria-hidden className="size-4 text-teal-300" />
        <h1 className="text-lg font-semibold">{project?.name ?? data.bundle?.project.name ?? pid}</h1>
        <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[11px] text-zinc-300">
          {pack === 'grid' ? 'Grid asset pack' : 'Solar asset pack'}
        </span>
      </header>
      {error && (
        <p role="alert" className="flex items-center gap-2 text-xs text-amber-200">
          <TriangleAlert aria-hidden className="size-3.5" /> {error}
        </p>
      )}
      {result ? (
        <AssetPackView pack={pack} result={result} onRerun={() => void rerun()} rerunning={busy} narration={narration} />
      ) : data.status === 'loading' ? (
        <EmptyState title="Loading…" />
      ) : (
        <EmptyState
          title="No recorded result for this asset pack"
          action={
            <Button size="sm" onClick={() => void rerun()} disabled={busy}>
              Run the {pack} engine
            </Button>
          }
        >
          {data.error ?? 'The static bundle has no evaluate_grid/evaluate_solar result.'}
        </EmptyState>
      )}
    </div>
  )
}
