/**
 * CourseOverview.vue: who gets editor links in the course outline.
 *
 * Instructors' `name` (a login email) is not sent to other viewers, so the
 * instructor rows a guest receives carry a `username` but no `name`. The page
 * used to compare `instructor.name === user.data?.name`; for a guest both sides
 * were undefined, the guest matched every instructor, and the outline linked
 * each lesson to the editor (?editLesson=…#editor), which shows a guest a blank
 * page. Matching must go through isInstructorOf (username, never empty).
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, reactive } from 'vue'
import { shallowMount } from '@vue/test-utils'
import CourseOverview from '@/pages/Courses/CourseOverview.vue'
import CourseOutline from '@/components/CourseOutline.vue'

type ResourceOpts = { url: string; makeParams?: () => Record<string, unknown> }

const resources: Array<Record<string, any>> = []

vi.mock('frappe-ui', async () => {
	const { reactive } = await import('vue')
	return {
		Badge: { template: '<span><slot /></span>' },
		createResource: (opts: ResourceOpts) => {
			const resource = reactive({
				...opts,
				data: null as unknown,
				loading: false,
				fetch: vi.fn(),
				reload: vi.fn(),
			})
			resources.push(resource)
			return resource
		},
	}
})
vi.mock('vue-router', () => ({
	useRoute: () => ({ query: {} }),
	useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))
vi.mock('@/utils/', () => ({
	formatAmount: (a: unknown) => String(a),
	formatRating: (r: unknown) => String(r),
}))
vi.mock('@/utils/sanitizeRichHTML', () => ({
	sanitizeRichHTML: (h: string) => h,
}))
vi.mock('@/components/CourseOutline.vue', () => ({
	default: {
		name: 'CourseOutline',
		props: ['courseName', 'getProgress', 'editorLinks'],
		template: '<div />',
	},
}))
for (const path of [
	'@/components/CourseCardOverlay.vue',
	'@/components/SkeletonLoader.vue',
	'@/components/CourseReviews.vue',
	'@/components/CourseInstructors.vue',
	'@/components/CourseCreatorCard.vue',
	'@/components/UserAvatar.vue',
	'@/components/RelatedCourses.vue',
]) {
	vi.doMock(path, () => ({ default: { template: '<div />' } }))
}

vi.stubGlobal('__', (s: string) => s)

// What a non-instructor receives: username and display fields, no `name`.
const course = () =>
	reactive({
		data: {
			name: 'class-10-mathematics',
			title: 'Class 10-Mathematics',
			instructors: [{ username: 'pankaj', full_name: 'Pankaj' }],
		},
	})

const mountAs = async (userData: Record<string, unknown> | null) => {
	const wrapper = shallowMount(CourseOverview, {
		props: { course: course() },
		global: {
			provide: { $user: { data: userData } },
			mocks: { __: (s: string) => s },
			stubs: { 'router-link': true },
		},
	})
	const outline = resources.find(
		(r) => r.url === 'lms.lms.utils.get_course_outline'
	)!
	outline.data = [{ name: 'CH-1', lessons: [{ name: 'L-1', number: '1-1' }] }]
	await nextTick()
	return wrapper.findComponent(CourseOutline)
}

beforeEach(() => {
	resources.length = 0
})

describe('CourseOverview editor links', () => {
	it('gives a guest student links, not editor links', async () => {
		const outline = await mountAs(null)
		expect(outline.exists()).toBe(true)
		expect(outline.props('editorLinks')).toBe(false)
	})

	it('gives a logged-in non-instructor student links', async () => {
		const outline = await mountAs({ name: 'student@x.com', username: 'student' })
		expect(outline.props('editorLinks')).toBe(false)
	})

	it('gives the course instructor editor links', async () => {
		const outline = await mountAs({ name: 'pankaj@x.com', username: 'pankaj' })
		expect(outline.props('editorLinks')).toBe(true)
	})

	it('gives a moderator editor links', async () => {
		const outline = await mountAs({
			name: 'mod@x.com',
			username: 'mod',
			is_moderator: true,
		})
		expect(outline.props('editorLinks')).toBe(true)
	})
})
