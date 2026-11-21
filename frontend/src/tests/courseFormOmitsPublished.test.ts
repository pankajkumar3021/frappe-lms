/**
 * CourseForm.vue: the settings form never sends `published`.
 *
 * The form saves the whole course document (last write wins) but has no publish
 * field. Sending the `published` value it loaded would flip a course a Moderator
 * published after the form opened back to draft, and the server now refuses any
 * change to `published` from someone who is not a Moderator. Publishing belongs to
 * the header's Publish toggle.
 */
import { describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { shallowMount } from '@vue/test-utils'
import CourseForm from '@/pages/Courses/CourseForm.vue'

const submit = vi.fn()

vi.mock('frappe-ui', () => ({
	toast: { success: vi.fn(), error: vi.fn() },
	createResource: () => ({ data: null, submit: vi.fn(), reload: vi.fn() }),
	createDocumentResource: () =>
		reactive({
			doc: {
				name: 'COURSE-1',
				title: 'Course',
				short_introduction: 'Intro',
				description: '<p>About</p>',
				published: 1,
				published_on: '2026-11-01',
				modified: '2026-11-01 10:00:00',
				instructors: [{ instructor: 'teacher@example.com' }],
				related_courses: [],
			},
			setValue: { submit },
			reload: vi.fn(),
		}),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/utils', () => ({
	getMetaInfo: () => ({ data: null, reload: vi.fn() }),
	updateMetaInfo: vi.fn(),
}))
vi.mock('@/utils/courseForm', () => ({ validateCourse: () => null }))
vi.mock('@/utils/exportCourse', () => ({ exportCourseAsZip: vi.fn() }))
vi.mock('@/utils/resource', () => ({
	reportAutosaveError: vi.fn(),
	resourceErrorMessage: () => '',
}))
vi.mock('@/composables/useKeyboardShortcuts', () => ({
	useKeyboardShortcuts: vi.fn(),
	saveShortcut: vi.fn(),
}))
// The child sections are not under test. Stubbing them keeps their imports
// (members settings, which reach @framework/ui) out of this file.
vi.mock('@/components/SkeletonLoader.vue', () => ({
	default: { template: '<div />' },
}))
vi.mock('@/components/Courses/CourseDetailsSection.vue', () => ({
	default: { template: '<div />' },
}))
vi.mock('@/components/Courses/CourseOverviewSection.vue', () => ({
	default: { template: '<div />' },
}))
vi.mock('@/pages/Courses/CoursePublishSettings.vue', () => ({
	default: { template: '<div />' },
}))
vi.mock('@framework/ui/telemetry/index', () => ({}))
vi.mock('@framework/ui/components/Onboarding/index', () => ({}))

vi.stubGlobal('__', (s: string) => s)

describe('CourseForm save payload', () => {
	it('does not send published or published_on', () => {
		const wrapper = shallowMount(CourseForm, {
			props: { course: { data: { name: 'COURSE-1' }, reload: vi.fn() } },
			global: {
				provide: { $user: { data: { name: 'teacher@example.com' } } },
				mocks: { __: (s: string) => s },
				config: { globalProperties: { $dialog: vi.fn() } },
			},
		})

		;(wrapper.vm as unknown as { submitCourse: () => void }).submitCourse()

		expect(submit).toHaveBeenCalledTimes(1)
		const payload = submit.mock.calls[0][0]
		expect(payload).not.toHaveProperty('published')
		expect(payload).not.toHaveProperty('published_on')
		expect(payload).not.toHaveProperty('modified')
		expect(payload.title).toBe('Course')
	})
})
