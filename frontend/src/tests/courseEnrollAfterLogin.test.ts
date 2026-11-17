/**
 * A guest who presses Enroll on a free course signs in (password or Google)
 * and comes back to the course page with ?enroll=1. The page finishes that
 * enrollment so they do not have to press Enroll a second time.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, reactive } from 'vue'
import { shallowMount } from '@vue/test-utils'

const { call, route, replace } = vi.hoisted(() => ({
	call: vi.fn((..._args: unknown[]) => Promise.resolve()),
	route: { query: {} as Record<string, string> },
	replace: vi.fn(),
}))

vi.mock('frappe-ui', () => ({
	Badge: { template: '<span><slot /></span>' },
	call,
	toast: { success: vi.fn(), warning: vi.fn() },
	createResource: () => ({ data: null, fetch: vi.fn(), reload: vi.fn() }),
}))
vi.mock('vue-router', () => ({
	useRoute: () => route,
	useRouter: () => ({ replace, push: vi.fn() }),
}))
vi.mock('@/utils/', () => ({
	formatAmount: (a: unknown) => String(a),
	formatRating: (r: unknown) => String(r),
}))
for (const c of [
	'CourseCardOverlay',
	'CourseOutline',
	'SkeletonLoader',
	'CourseReviews',
	'CourseInstructors',
	'CourseCreatorCard',
	'UserAvatar',
	'RelatedCourses',
]) {
	vi.doMock(`@/components/${c}.vue`, () => ({
		default: { template: '<div />' },
	}))
}
vi.stubGlobal('__', (s: string) => s)

import CourseOverview from '@/pages/Courses/CourseOverview.vue'
import {
	canSelfEnroll,
	loginToEnrollUrl,
} from '@/composables/useCourseEnrollment'

const learner = { name: 'learner@example.com', username: 'learner' }
const freeCourse = { name: 'COURSE-1', instructors: [], tags: '' }

const mountOverview = (
	course: Record<string, unknown> | null,
	user: Record<string, unknown> | null = learner
) =>
	shallowMount(CourseOverview, {
		props: { course: reactive({ data: course }) } as never,
		global: {
			provide: { $user: reactive({ data: user }) },
			mocks: { __: (s: string) => s },
			stubs: { 'router-link': true },
		},
	})

const enrollCalls = () =>
	call.mock.calls.filter(([method]) => method === 'frappe.client.insert')

beforeEach(() => {
	call.mockClear()
	replace.mockClear()
	route.query = {}
})

describe('login link from the Enroll button', () => {
	it('returns to the course page with the enroll flag', () => {
		expect(loginToEnrollUrl('/lms/courses/COURSE-1')).toBe(
			'/login?redirect-to=%2Flms%2Fcourses%2FCOURSE-1%3Fenroll%3D1'
		)
	})
})

describe('canSelfEnroll', () => {
	it('allows a free course the learner is not in', () => {
		expect(canSelfEnroll(freeCourse as never, learner)).toBe(true)
	})

	it.each([
		['already enrolled', { membership: { progress: 0 } }],
		['paid', { paid_course: 1 }],
		['self-learning off', { disable_self_learning: 1 }],
		['taught by the learner', { instructors: [{ username: 'learner' }] }],
	])('refuses a course that is %s', (_label, extra) => {
		expect(canSelfEnroll({ ...freeCourse, ...extra } as never, learner)).toBe(
			false
		)
	})

	it('refuses a guest', () => {
		expect(canSelfEnroll(freeCourse as never, null as never)).toBe(false)
	})
})

describe('course page after login', () => {
	it('enrolls the learner once and drops the flag', async () => {
		route.query = { enroll: '1', ref: 'x' }
		mountOverview(freeCourse)
		await nextTick()

		expect(enrollCalls()).toHaveLength(1)
		expect(enrollCalls()[0][1]).toEqual({
			doc: {
				doctype: 'LMS Enrollment',
				course: 'COURSE-1',
				member: 'learner@example.com',
			},
		})
		expect(replace).toHaveBeenCalledWith({ query: { ref: 'x' } })
	})

	it('waits for the course to load before enrolling', async () => {
		route.query = { enroll: '1' }
		const wrapper = mountOverview(null)
		expect(enrollCalls()).toHaveLength(0)

		await wrapper.setProps({ course: reactive({ data: freeCourse }) } as never)
		await nextTick()
		expect(enrollCalls()).toHaveLength(1)
	})

	it('does nothing without the flag', async () => {
		mountOverview(freeCourse)
		await nextTick()
		expect(enrollCalls()).toHaveLength(0)
	})

	it('does not enroll in a paid course', async () => {
		route.query = { enroll: '1' }
		mountOverview({ ...freeCourse, paid_course: 1 })
		await nextTick()
		expect(enrollCalls()).toHaveLength(0)
		expect(replace).toHaveBeenCalled()
	})
})
