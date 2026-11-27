import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const h = vi.hoisted(() => ({
	callMock: vi.fn(),
	replaceMock: vi.fn(),
	reloadMock: vi.fn(),
}))

vi.mock('frappe-ui', async (importOriginal) => ({
	...(await importOriginal<typeof import('frappe-ui')>()),
	call: h.callMock,
	usePageMeta: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ replace: h.replaceMock }) }))
vi.mock('@/stores/user', () => ({
	usersStore: () => ({ userResource: { reload: h.reloadMock } }),
}))

const STATE = {
	needs_registration: true,
	classes: ['Class 9', 'Class 10'],
	cities: ['Delhi', 'Noida'],
	prefill: { full_name: 'Asha Rao', contact_number: '' },
}

// The registration state is cached per app load, so each test gets a fresh module.
async function mountPage() {
	vi.resetModules()
	const Registration = (await import('@/pages/Registration.vue')).default
	const wrapper = mount(Registration, {
		attachTo: document.body,
		global: { mocks: { __: (s: string) => s } },
	})
	await flushPromises()
	return wrapper
}

const button = (w: any) => w.get('button[type="submit"]')

// frappe-ui's select is a Reka combobox that jsdom cannot open, so the test
// sets the value through the control's own v-model event.
const pick = async (w: any, index: number, value: string) => {
	const selects = w
		.findAllComponents({ name: 'FormControl' })
		.filter((c: any) => c.props('type') === 'select')
	selects[index].vm.$emit('update:modelValue', value)
	await w.vm.$nextTick()
}

async function fillValid(w: any) {
	await w.get('input[type="text"][inputmode="tel"]').setValue('98765 43210')
	await pick(w, 0, 'Class 10')
	await pick(w, 1, 'Noida')
	await w.findAll('input[type="checkbox"]')[0].setValue(true)
}

beforeEach(() => {
	h.callMock.mockReset()
	h.replaceMock.mockReset()
	h.reloadMock.mockReset()
	h.callMock.mockImplementation(async (method: string) =>
		method.endsWith('get_registration_state')
			? STATE
			: { student_class: 'Class 10' },
	)
})

describe('Registration page', () => {
	it('prefills the name and shows the page copy', async () => {
		const w = await mountPage()

		expect(w.get('h1').text()).toBe('Tell us about yourself')
		expect(
			(w.get('input[type="text"]').element as HTMLInputElement).value,
		).toBe('Asha Rao')
		expect(w.text()).toContain("I'm interested in")
		expect(w.text()).toContain('Online courses')
		expect(w.text()).toContain('Classroom courses')
		expect(button(w).text()).toBe('Continue')
		w.unmount()
	})

	it('keeps Continue disabled until every field is set', async () => {
		const w = await mountPage()
		expect(button(w).attributes('disabled')).toBeDefined()

		await w.get('input[type="text"][inputmode="tel"]').setValue('12345')
		await pick(w, 0, 'Class 10')
		await pick(w, 1, 'Noida')
		await w.findAll('input[type="checkbox"]')[0].setValue(true)
		expect(button(w).attributes('disabled')).toBeDefined()

		await w
			.get('input[type="text"][inputmode="tel"]')
			.setValue('+91 98765 43210')
		expect(button(w).attributes('disabled')).toBeUndefined()

		await w.findAll('input[type="checkbox"]')[0].setValue(false)
		expect(button(w).attributes('disabled')).toBeDefined()
		w.unmount()
	})

	it.each([
		['09876543210', false],
		['(98765) 43210', false],
		['919876543210', false],
		['5876543210', true],
		['1234567890', true],
	])('checks the mobile number %s like the server', async (number, invalid) => {
		const w = await mountPage()
		await pick(w, 0, 'Class 10')
		await pick(w, 1, 'Noida')
		await w.findAll('input[type="checkbox"]')[0].setValue(true)
		await w.get('input[type="text"][inputmode="tel"]').setValue(number)
		expect(button(w).attributes('disabled') !== undefined).toBe(invalid)
		w.unmount()
	})

	it('submits the values and opens Courses filtered to the class', async () => {
		const w = await mountPage()
		await fillValid(w)
		await w.get('form').trigger('submit')
		await flushPromises()

		expect(h.callMock).toHaveBeenCalledWith(
			'lms.lms.registration.submit_registration',
			{
				full_name: 'Asha Rao',
				contact_number: '98765 43210',
				student_class: 'Class 10',
				city: 'Noida',
				wants_online: 1,
				wants_classroom: 0,
			},
		)
		expect(h.reloadMock).toHaveBeenCalled()
		expect(h.replaceMock).toHaveBeenCalledWith({
			name: 'Courses',
			query: { class: 'Class 10' },
		})
		w.unmount()
	})

	it('shows the server error and stays on the form', async () => {
		h.callMock.mockImplementation(async (method: string) => {
			if (method.endsWith('get_registration_state')) return STATE
			throw { messages: ['You are already registered.'] }
		})
		const w = await mountPage()
		await fillValid(w)
		await w.get('form').trigger('submit')
		await flushPromises()

		expect(w.get('[role="alert"]').text()).toBe('You are already registered.')
		expect(h.replaceMock).not.toHaveBeenCalled()
		w.unmount()
	})

	it('labels every control (a11y)', async () => {
		const w = await mountPage()
		const controls = w.findAll('input, [role="combobox"]')
		expect(controls.length).toBe(6)
		for (const control of controls) {
			const el = control.element as HTMLInputElement
			const named =
				(el.labels && el.labels.length > 0) ||
				el.getAttribute('aria-label') ||
				el.getAttribute('aria-labelledby')
			expect(named, el.outerHTML).toBeTruthy()
		}
		expect(w.findAll('h1')).toHaveLength(1)
		w.unmount()
	})
})
