// Tabs in the top bar. Navigation uses the URL hash (#/encode, #/library) so
// refresh and the back button work without a router dependency.
export const TABS = [
  { id: 'encode', label: 'Encode', href: '#/encode' },
  { id: 'library', label: 'Library', href: '#/library' },
] as const

export type TabId = (typeof TABS)[number]['id']

export function tabFromHash(hash: string): TabId {
  return TABS.find((tab) => tab.href === hash)?.id ?? 'encode'
}
