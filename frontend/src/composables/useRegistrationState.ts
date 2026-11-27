import { call } from 'frappe-ui'

export type RegistrationState = {
	needs_registration: boolean
	classes: string[]
	cities: string[]
	prefill: { full_name: string; contact_number: string }
}

// One state call per app load. A failed call is not cached, so the next
// navigation asks again, as the setup check does.
let pending: Promise<RegistrationState> | null = null

export function useRegistrationState() {
	function getState(): Promise<RegistrationState> {
		if (!pending) {
			pending = call('lms.lms.registration.get_registration_state').catch(
				(error: unknown) => {
					pending = null
					throw error
				},
			)
		}
		return pending
	}

	async function needsRegistration(): Promise<boolean> {
		try {
			return Boolean((await getState()).needs_registration)
		} catch (_) {
			return false
		}
	}

	// Keep the cached class and city lists: the Courses page reads them right after
	// registration in the same app load.
	function markRegistered() {
		const empty: RegistrationState = {
			needs_registration: false,
			classes: [],
			cities: [],
			prefill: { full_name: '', contact_number: '' },
		}
		const previous = pending ?? Promise.resolve(empty)
		pending = previous.then(
			(state) => ({ ...state, needs_registration: false }),
			() => empty,
		)
	}

	return { getState, needsRegistration, markRegistered }
}
