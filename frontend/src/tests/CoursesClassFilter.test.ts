import { describe, expect, it, vi, beforeEach } from 'vitest'
import { nextTick, reactive } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'

const { listResource, classNames } = vi.hoisted(() => ({
	listResource: { current: null as any },
	classNames: ['Class 9', 'Class 10', 'Class 12 PCM'],
}))

vi.mock('frappe-ui', () => ({
	usePageMeta: vi.fn(),
	createResource: () => reactive({ data: 0, abort: vi.fn(), submit: vi.fn() }),
	createListResource: (options: { url: string }) =>
		options.url.includes('get_course_categories')
			? reactive({ data: [], list: { loading: false }, reload: vi.fn() })
			: listResource.current,
	Button: { template: '<button><slot /></button>' },
	Dropdown: { template: '<div><slot :open="false" /></div>' },
	FormControl: { template: '<input />' },
	TabButtons: { template: '<div />' },
}))
vi.mock('@/composables/useRegistrationState', () => ({
	useRegistrationState: () => ({
		getState: () => Promise.resolve({ classes: classNames }),
	}),
}))
vi.mock('@framework/ui/telemetry/index', () => ({
	useTelemetry: () => ({ capture: vi.fn() }),
}))
vi.mock('@/stores/session', () => ({ sessionStore: () => ({ brand: {} }) }))
vi.mock('@/utils', () => ({ canCreateCourse: () => false }))
vi.mock('vue-router', () => ({
	useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))
vi.mock('@/components/CourseCard.vue', () => ({
	default: { template: '<article />' },
}))
vi.mock('@/components/Controls/ToggleFilter.vue', () => ({
	default: { template: '<div />' },
}))
vi.mock('@/components/Controls/ClearableCombobox.vue', () => ({
	default: {
		props: ['modelValue', 'options', 'ariaLabel'],
		emits: ['update:modelValue'],
		template: `<select :data-testid="ariaLabel" :value="modelValue"
			@change="$emit('update:modelValue', $event.target.value)">
			<option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
		</select>`,
	},
}))
vi.mock('@/components/Layouts/pages/ListPage.vue', () => ({
	default: {
		props: ['filtered'],
		template:
			'<div :data-filtered="String(filtered)"><slot name="filters" /></div>',
	},
}))
vi.stubGlobal('__', (s: string) => s)

async function mountCourses(userData: Record<string, unknown> | null) {
	const { default: Courses } = await import('@/pages/Courses/Courses.vue')
	const wrapper = mount(Courses, {
		global: {
			provide: {
				$user: { data: userData },
				$dayjs: () => ({ add: () => ({ format: () => '' }) }),
			},
			mocks: { __: (s: string) => s },
			stubs: { 'router-view': true },
		},
	})
	await flushPromises()
	return wrapper
}

const sent = () => listResource.current.filters
const select = (w: any) => w.find('[data-testid="Class"]')

beforeEach(() => {
	window.history.replaceState({}, '', '/lms/courses')
	listResource.current = reactive({
		data: [],
		hasNextPage: false,
		pageLength: 24,
		filters: {},
		list: { loading: false, abort: vi.fn() },
		update({ filters }: any) {
			this.filters = JSON.parse(JSON.stringify(filters))
		},
		reload: vi.fn(),
		next: vi.fn(),
	})
	vi.resetModules()
})

describe('Courses class filter', () => {
	it("starts on the student's class", async () => {
		const w = await mountCourses({ name: 'a@b.c', student_class: 'Class 10' })
		expect(sent().class).toBe('Class 10')
		expect((select(w).element as HTMLSelectElement).value).toBe('Class 10')
		expect(w.find('[data-filtered]').attributes('data-filtered')).toBe('true')
	})

	it('lets ?class= win over the student class', async () => {
		window.history.replaceState({}, '', '/lms/courses?class=Class+12+PCM')
		const w = await mountCourses({ name: 'a@b.c', student_class: 'Class 10' })
		expect(sent().class).toBe('Class 12 PCM')
		expect((select(w).element as HTMLSelectElement).value).toBe('Class 12 PCM')
	})

	it('All classes drops the filter and keeps ?class=all in the URL', async () => {
		const w = await mountCourses({ name: 'a@b.c', student_class: 'Class 10' })
		await select(w).setValue('all')
		await nextTick()
		expect(sent()).not.toHaveProperty('class')
		expect(new URLSearchParams(location.search).get('class')).toBe('all')
	})

	it('honours ?class=all on load', async () => {
		window.history.replaceState({}, '', '/lms/courses?class=all')
		await mountCourses({ name: 'a@b.c', student_class: 'Class 10' })
		expect(sent()).not.toHaveProperty('class')
	})

	it('puts no class filter on a guest', async () => {
		await mountCourses(null)
		expect(sent()).not.toHaveProperty('class')
		expect(location.search).not.toContain('class')
	})
})
