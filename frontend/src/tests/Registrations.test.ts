import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'

const { call, toast } = vi.hoisted(() => ({
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('frappe-ui', () => ({
	call,
	toast,
	usePageMeta: vi.fn(),
	Button: {
		props: ['loading'],
		template: '<button @click="$emit(\'click\')"><slot /></button>',
	},
	FormControl: {
		props: ['modelValue', 'label', 'type', 'options'],
		emits: ['update:modelValue'],
		template: `<select v-if="type === 'select'" :data-testid="label" :value="modelValue"
				@change="$emit('update:modelValue', $event.target.value)">
				<option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
			</select>
			<textarea v-else :data-testid="label" :value="modelValue"
				@input="$emit('update:modelValue', $event.target.value)" />`,
	},
	Dialog: {
		props: ['open'],
		template: '<div v-if="open"><slot /><slot name="actions" /></div>',
	},
}))
vi.mock('@/composables/useRegistrationState', () => ({
	useRegistrationState: () => ({
		getState: () =>
			Promise.resolve({
				classes: ['Class 9', 'Class 10'],
				cities: ['Delhi', 'Noida'],
			}),
	}),
}))
vi.mock('@/stores/session', () => ({ sessionStore: () => ({ brand: {} }) }))
vi.mock('@/components/Controls/ClearableCombobox.vue', () => ({
	default: {
		props: ['modelValue', 'options', 'ariaLabel'],
		emits: ['update:modelValue'],
		template: `<select :data-testid="ariaLabel" :value="modelValue ?? ''"
			@change="$emit('update:modelValue', $event.target.value || null)">
			<option value=""></option>
			<option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
		</select>`,
	},
}))
vi.mock('@/components/Controls/ToggleFilter.vue', () => ({
	default: {
		props: ['modelValue', 'label'],
		emits: ['update:modelValue'],
		template: `<input type="checkbox" :data-testid="label" :checked="modelValue"
			@change="$emit('update:modelValue', $event.target.checked)" />`,
	},
}))
vi.mock('@/components/Layouts/pages/ListPage.vue', () => ({
	default: {
		props: ['rows', 'listOptions', 'columns'],
		template: `<div><slot name="filters" />
			<div v-for="row in rows" :key="row.name" data-row @click="listOptions.onRowClick(row)">
				<slot name="cell" :column="{ key: 'contact_number' }" :row="row" :value="row.contact_number" />
			</div></div>`,
	},
}))
vi.stubGlobal('__', (s: string) => s)

const ROW = {
	name: 'REG-1',
	full_name: 'Asha',
	contact_number: '+919876543210',
	student_class: 'Class 9',
	city: 'Delhi',
	wants_online: 1,
	wants_classroom: 1,
	follow_up_status: 'New',
	assigned_to: null,
	assigned_to_name: '',
	follow_up_notes: '',
	registered_on: '2026-11-20 10:00:00',
}

const listCalls = () =>
	call.mock.calls.filter(
		([m]) => m === 'lms.lms.registration.get_registrations',
	)
const lastFilters = () => listCalls().at(-1)![1].filters

async function mountPage() {
	const { default: Registrations } = await import('@/pages/Registrations.vue')
	const wrapper = mount(Registrations, {
		global: {
			mocks: { __: (s: string) => s },
			provide: {
				$user: reactive({ data: { name: 'team@example.com' } }),
				$dayjs: () => ({ format: () => '20 Nov 2026' }),
			},
		},
	})
	await flushPromises()
	return wrapper
}

const field = (w: any, id: string) => w.find(`[data-testid="${id}"]`)

beforeEach(() => {
	call.mockReset()
	toast.success.mockReset()
	toast.error.mockReset()
	call.mockImplementation(async (method: string) => {
		if (method.endsWith('get_registrations')) return { rows: [ROW], count: 1 }
		if (method.endsWith('get_registration_team'))
			return [{ value: 'team@example.com', label: 'Team Member' }]
		return {}
	})
	vi.resetModules()
})

describe('Registrations page', () => {
	it('loads New, classroom registrations by default', async () => {
		await mountPage()
		expect(listCalls()).toHaveLength(1)
		expect(lastFilters()).toEqual({
			follow_up_status: 'New',
			wants_classroom: 1,
		})
	})

	it('re-queries when status, class, city and Assigned to me change', async () => {
		const w = await mountPage()
		await field(w, 'Status').setValue('Contacted')
		await flushPromises()
		expect(lastFilters().follow_up_status).toBe('Contacted')
		await field(w, 'Class').setValue('Class 10')
		await flushPromises()
		expect(lastFilters().student_class).toBe('Class 10')
		await field(w, 'City').setValue('Noida')
		await flushPromises()
		expect(lastFilters().city).toBe('Noida')
		await field(w, 'Assigned to me').setValue(true)
		await flushPromises()
		expect(lastFilters().assigned_to).toBe('team@example.com')
		await field(w, 'Classroom only').setValue(false)
		await flushPromises()
		expect(lastFilters()).not.toHaveProperty('wants_classroom')
	})

	it('renders the phone number as a tel link', async () => {
		const w = await mountPage()
		expect(w.find('a').attributes('href')).toBe('tel:+919876543210')
	})

	it('saves only the three editable fields and reloads', async () => {
		const w = await mountPage()
		await w.find('[data-row]').trigger('click')
		// The dialog's Status select comes after the list filter of the same name.
		await w.findAll('[data-testid="Status"]').at(-1)!.setValue('Contacted')
		await field(w, 'Assigned to').setValue('team@example.com')
		await field(w, 'Notes').setValue('Called, will join')
		const before = listCalls().length
		await w.findAll('button').at(-1)!.trigger('click')
		await flushPromises()
		const update = call.mock.calls.find(([m]) =>
			m.endsWith('update_registration'),
		)!
		expect(update[1]).toEqual({
			name: 'REG-1',
			follow_up_status: 'Contacted',
			assigned_to: 'team@example.com',
			follow_up_notes: 'Called, will join',
		})
		expect(listCalls().length).toBe(before + 1)
	})
})

describe('Registrations route guard', () => {
	async function enter(canManage: boolean | undefined) {
		vi.doMock('@/stores/user', () => ({
			usersStore: () => ({
				userResource: { data: { can_manage_registrations: canManage } },
			}),
		}))
		const { routes } = await import('@/routes')
		const route = routes.find((r) => r.name === 'Registrations')!
		return (route as any).beforeEnter()
	}

	it('lets the team in', async () => {
		expect(await enter(true)).toBe(true)
	})

	it('sends everyone else to Home', async () => {
		expect(await enter(false)).toEqual({ name: 'Home' })
		expect(await enter(undefined)).toEqual({ name: 'Home' })
	})
})
