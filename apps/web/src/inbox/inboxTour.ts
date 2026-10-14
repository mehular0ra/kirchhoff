// Optional tour hook (spec §20). It is NOT in TOUR_STEPS: the 7-step tour (spec §13.5) keeps its order. It has the
// shape of P3 Task 14's TourStep, so an extras tour or a hint can use it; its target is the dashboard's inbox entry.
export const INBOX_TOUR_STEP = {
  id: 'inbox',
  route: () => '/app',
  target: '[data-tour="inbox"]',
  title: () => 'Bids start in the inbox',
  body: 'Kirchhoff triages every email to bids@: it classifies the attachments, verifies the quotes, checks fit and supply, and opens the project.',
}
