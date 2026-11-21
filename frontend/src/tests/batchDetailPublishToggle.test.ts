/**
 * BatchDetail.vue: only a Moderator sees the Publish / Unpublish toggle.
 *
 * The server refuses a change to a batch's `published` from anyone else. An
 * instructor or evaluator still manages the batch (and sees its other settings
 * actions) but must not be offered a toggle that would only fail.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { defineComponent, h } from 'vue'

vi.stubGlobal('__', (text: string) => text)

const { batchResource, createResourceMock } = vi.hoisted(() => ({
	batchResource: {
		data: null as Record<string, unknown> | null,
		loading: false,
		fetched: true,
		error: null,
		reload: vi.fn(),
		submit: vi.fn(),
	},
	createResourceMock: vi.fn(),
}))

vi.mock('frappe-ui', () => ({
	createResource: createResourceMock,
	usePageMeta: () => {},
	toast: { success: vi.fn(), error: vi.fn() },
	Badge: { template: `<span><slot /></span>` },
	Tooltip: { template: `<div><slot /></div>` },
	Button: { template: `<button data-testid="header-button"><slot /></button>` },
	Dropdown: { template: `<div />` },
}))

vi.mock('@/stores/session', () => ({
	sessionStore: () => ({ brand: { favicon: '' } }),
}))

const { inert } = vi.hoisted(() => ({
	inert: () => ({ default: { render: () => null } }),
}))
vi.mock('@/pages/Batches/components/AdminBatchDashboard.vue', inert)
vi.mock('@/pages/Batches/components/BatchDashboard.vue', inert)
vi.mock('@/pages/Batches/BatchOverview.vue', inert)
vi.mock('@/pages/Batches/components/LiveClass.vue', inert)
vi.mock('@/pages/Batches/components/Announcements.vue', inert)
vi.mock('@/pages/Batches/BatchForm.vue', inert)
vi.mock('@/components/Discussions.vue', inert)
vi.mock('@/components/SkeletonLoader.vue', inert)
vi.mock('@/components/ShortcutTooltip.vue', inert)
vi.mock('@/components/HeaderButton.vue', inert)
// Render the header actions for the Settings tab, where the toggle lives.
vi.mock('@/components/Layouts/pages/TabbedDetailPage.vue', () => ({
	default: {
		props: ['tabs', 'breadcrumbs', 'published', 'loading', 'doc', 'docProp'],
		template: `<div><slot name="actions" :tab="{ key: 'settings' }" /></div>`,
	},
}))

// @ts-expect-error a JS SFC has no generated types (TS7016)
import BatchDetail from '@/pages/Batches/BatchDetail.vue'

const publishButtonsFor = async (user: Record<string, unknown>) => {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{
				path: '/batches/:batchName',
				name: 'BatchDetail',
				component: BatchDetail,
				props: true,
			},
		],
	})
	await router.push('/batches/B1')
	const wrapper = mount(defineComponent({ render: () => h(RouterView) }), {
		global: {
			plugins: [router],
			provide: { $user: { data: user } },
			mocks: { __: (text: string) => text },
		},
	})
	await flushPromises()
	return wrapper
		.findAll('[data-testid="header-button"]')
		.map((b) => b.text())
		.filter((text) => text === 'Publish' || text === 'Unpublish')
}

describe("BatchDetail's Publish toggle", () => {
	beforeEach(() => {
		createResourceMock.mockReset()
		createResourceMock.mockReturnValue(batchResource)
		batchResource.data = { name: 'B1', title: 'B', published: 0, can_manage: 1 }
	})

	it('is shown to a Moderator', async () => {
		expect(
			await publishButtonsFor({ name: 'mod@example.com', is_moderator: true })
		).toEqual(['Publish'])
	})

	it('is hidden from an instructor who manages the batch', async () => {
		expect(
			await publishButtonsFor({ name: 'teacher@example.com', is_instructor: true })
		).toEqual([])
	})

	it('is hidden from an evaluator', async () => {
		expect(
			await publishButtonsFor({ name: 'eval@example.com', is_evaluator: true })
		).toEqual([])
	})
})
