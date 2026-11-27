import { describe, expect, it, vi, beforeEach } from 'vitest'

const state = vi.hoisted(() => ({
	isLoggedIn: true,
	isStudent: true,
	callMock: vi.fn(),
}))

vi.mock('frappe-ui', () => ({ call: state.callMock }))
vi.mock('@/stores/session', () => ({
	sessionStore: () => ({
		get isLoggedIn() {
			return state.isLoggedIn
		},
	}),
}))
vi.mock('@/stores/user', () => ({
	usersStore: () => ({
		userResource: {
			promise: Promise.resolve(),
			data: { is_student: state.isStudent },
		},
	}),
}))
vi.mock('@/stores/settings', () => ({
	useSettings: () => ({
		settings: {
			promise: Promise.resolve(),
			data: { allow_guest_access: 1 },
		},
	}),
}))

const coursesRoute = { name: 'Courses', path: '/courses' } as any
const registrationRoute = { name: 'Registration', path: '/registration' } as any

// The state is cached per app load, so each test gets a fresh router module.
async function loadGuard() {
	vi.resetModules()
	return (await import('@/router')).guardNavigation
}

const stateCalls = () =>
	state.callMock.mock.calls.filter(
		([method]) => method === 'lms.lms.registration.get_registration_state',
	)

beforeEach(() => {
	state.isLoggedIn = true
	state.isStudent = true
	state.callMock.mockReset()
	state.callMock.mockResolvedValue({ needs_registration: true })
})

describe('registration guard', () => {
	it('sends a student who needs registration to the form', async () => {
		const guard = await loadGuard()
		const next = vi.fn()
		await guard(coursesRoute, {}, next)

		expect(next).toHaveBeenCalledWith({ name: 'Registration' })
	})

	it('lets them stay on the form, so the gate cannot loop', async () => {
		const guard = await loadGuard()
		const next = vi.fn()
		await guard(registrationRoute, { name: 'Courses', path: '/courses' }, next)

		expect(next).toHaveBeenCalledWith()
	})

	it('lets the user through when the state call fails', async () => {
		state.callMock.mockRejectedValue(new Error('offline'))
		const guard = await loadGuard()
		const next = vi.fn()
		await guard(coursesRoute, {}, next)

		expect(next).toHaveBeenCalledWith()
	})

	it('lets a registered student through', async () => {
		state.callMock.mockResolvedValue({ needs_registration: false })
		const guard = await loadGuard()
		const next = vi.fn()
		await guard(coursesRoute, {}, next)

		expect(next).toHaveBeenCalledWith()
	})

	it('asks the server once per app load', async () => {
		const guard = await loadGuard()
		await guard(coursesRoute, {}, vi.fn())
		await guard({ name: 'Batches', path: '/batches' } as any, {}, vi.fn())

		expect(stateCalls()).toHaveLength(1)
	})

	it('never asks for a guest', async () => {
		state.isLoggedIn = false
		const guard = await loadGuard()
		const next = vi.fn()
		await guard(coursesRoute, {}, next)

		expect(next).toHaveBeenCalledWith()
		expect(stateCalls()).toHaveLength(0)
	})

	it('never asks for a user who is not a student', async () => {
		state.isStudent = false
		const guard = await loadGuard()
		const next = vi.fn()
		await guard(coursesRoute, {}, next)

		expect(next).toHaveBeenCalledWith()
		expect(stateCalls()).toHaveLength(0)
	})
})

describe('markRegistered', () => {
	it('keeps the cached class list while clearing needs_registration', async () => {
		vi.resetModules()
		state.callMock.mockResolvedValue({
			needs_registration: true,
			classes: ['Class 10'],
			cities: ['Delhi'],
			prefill: { full_name: '', contact_number: '' },
		})
		const { useRegistrationState } =
			await import('@/composables/useRegistrationState')
		const { getState, markRegistered } = useRegistrationState()
		await getState()
		markRegistered()
		expect(await getState()).toMatchObject({
			needs_registration: false,
			classes: ['Class 10'],
			cities: ['Delhi'],
		})
	})
})
