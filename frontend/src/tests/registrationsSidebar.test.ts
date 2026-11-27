import { describe, expect, it, vi } from 'vitest'

const { user } = vi.hoisted(() => ({
	user: { data: undefined as Record<string, unknown> | undefined },
}))

vi.mock('plyr', () => ({ default: class {} }))
vi.mock('@/stores/user', () => ({ usersStore: () => ({ userResource: user }) }))
vi.mock('@/stores/settings', () => ({
	useSettings: () => ({ settings: { data: {} }, programs: { data: null } }),
}))
vi.mock('@/router', () => ({ default: {} }))
vi.stubGlobal('__', (s: string) => s)

import { getSidebarLinks } from '@/utils'

const labels = () =>
	getSidebarLinks().flatMap((group: any) =>
		group.items.map((i: any) => i.label),
	)

describe('sidebar Registrations link', () => {
	it('shows for the follow-up team', () => {
		user.data = { can_manage_registrations: true }
		expect(labels()).toContain('Registrations')
	})

	it.each([
		['a student', { can_manage_registrations: false }],
		['a guest', undefined],
	])('hides for %s', (_, data) => {
		user.data = data
		expect(labels()).not.toContain('Registrations')
	})
})
