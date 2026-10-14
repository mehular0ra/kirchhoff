// Bids inbox (spec §20) at /app/inbox and /app/inbox/:emailId: the email list and one email's detail. Static first
// (/demo/inbox.json), live second (GET /api/inbox). Keyboard: every row is a link; the detail's controls are buttons.
import { cn } from 'cn'
import { Handshake, Inbox, Mail, Paperclip } from 'lucide-react'
import { useEffect } from 'react'
import { Link, useParams } from 'react-router'
import { EmptyState, SandboxLabel } from '@/components/Labels'
import { fmtRelative } from '@/lib/format'
import type { InboxEmail } from '@/lib/types'
import { EmailDetail, VerdictBadge } from './EmailDetail'
import { appetiteLine } from './inboxMeta'
import { markRead, useInbox } from './useInbox'

function EmailRow({ email, unread, active }: { email: InboxEmail; unread: boolean; active: boolean }) {
  return (
    <li className={cn('border-b', active && 'bg-accent')}>
      <Link
        to={`/app/inbox/${email.id}`}
        aria-current={active ? 'true' : undefined}
        className="flex flex-col gap-1 px-4 py-3 hover:bg-zinc-800/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sky-400"
      >
        <span className="flex items-center gap-2 text-sm">
          {unread && (
            <span className="inline-flex items-center gap-1 rounded bg-sky-500/15 px-1.5 text-[11px] font-medium text-sky-200">
              <Mail aria-hidden className="size-3" />
              New
            </span>
          )}
          <span className={cn('truncate', unread ? 'font-semibold text-zinc-100' : 'text-zinc-300')}>{email.from_org}</span>
          <span className="ml-auto shrink-0 text-xs text-zinc-500">{fmtRelative(email.received_at)}</span>
        </span>
        <span className="truncate text-sm text-zinc-300">{email.subject}</span>
        <span className="flex items-center gap-2 text-xs text-zinc-400">
          {email.triage ? <VerdictBadge triage={email.triage} /> : <span>Not triaged yet</span>}
          {email.attachments.length > 0 && (
            <span className="inline-flex items-center gap-1">
              <Paperclip aria-hidden className="size-3" />
              {email.attachments.length}
            </span>
          )}
          {email.status === 'pursued' && (
            <span className="inline-flex items-center gap-1 text-emerald-300">
              <Handshake aria-hidden className="size-3" />
              Pursued
            </span>
          )}
        </span>
      </Link>
    </li>
  )
}

export function InboxPage() {
  const { emailId } = useParams()
  const { data, live, error, read } = useInbox()
  useEffect(() => {
    if (emailId) markRead(emailId)
  }, [emailId])
  if (error) return <EmptyState title="Could not load the bids inbox">{error}</EmptyState>
  if (!data) return <EmptyState title="Loading the bids inbox…" />
  const selected = data.emails.find((e) => e.id === emailId) ?? null
  return (
    <div className="mx-auto grid h-full max-w-7xl grid-cols-1 lg:grid-cols-[24rem_1fr]">
      <section aria-labelledby="inbox-h" className={cn('flex min-h-0 flex-col border-r', emailId && 'hidden lg:flex')}>
        <header className="flex flex-col gap-1 border-b p-4">
          <div className="flex items-center gap-2">
            <Inbox aria-hidden className="size-4 text-sky-300" />
            <h1 id="inbox-h" className="text-lg font-semibold">
              Bids inbox
            </h1>
            <SandboxLabel className="ml-auto" />
          </div>
          <p className="font-mono text-xs text-zinc-400">{data.mailbox}</p>
          <p className="text-xs text-zinc-500">{live ? 'Live · your workspace' : 'Recorded triage (static)'}</p>
          <p className="text-xs text-zinc-500">{appetiteLine(data.appetite)}</p>
        </header>
        <ol aria-label="Emails" className="min-h-0 flex-1 overflow-auto">
          {data.emails.map((e) => (
            <EmailRow key={e.id} email={e} unread={!read.includes(e.id)} active={e.id === emailId} />
          ))}
        </ol>
      </section>
      <section aria-label="Email" className={cn('min-h-0 overflow-auto', !emailId && 'hidden lg:block')}>
        {selected ? (
          <EmailDetail email={selected} />
        ) : (
          <EmptyState title={emailId ? 'Email not found' : 'Select an email'}>
            Kirchhoff triages every email to the bids mailbox: it classifies the attachments, verifies the quotes,
            checks fit and supply, and opens the project.
          </EmptyState>
        )}
      </section>
    </div>
  )
}
