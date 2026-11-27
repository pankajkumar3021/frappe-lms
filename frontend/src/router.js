import { createRouter, createWebHistory } from 'vue-router'
import { call } from 'frappe-ui'
import { usersStore } from './stores/user'
import { sessionStore } from './stores/session'
import { useSettings } from './stores/settings'
import { getLmsBasePath } from './utils/basePath'
import { routes } from './routes'
import { useRegistrationState } from './composables/useRegistrationState'

// Run the fresh-site-admin setup check at most once per app load.
let setupChecked = false

// Learning's setup page, or the desk wizard while the site itself is not set up yet.
async function setupRoute(developerMode) {
	const state = await call('lms.lms.onboarding.get_setup_state')
	if (!state?.needs_setup) return null
	// A developer's own site skips the questions and the desk wizard, never the password.
	if (developerMode) return state.needs_password ? { name: 'Setup' } : null
	if (state.setup_url) {
		window.location.href = state.setup_url
		return false
	}
	return { name: 'Setup' }
}

let router = createRouter({
	history: createWebHistory(`/${getLmsBasePath()}`),
	routes,
})

export async function guardNavigation(to, from, next) {
	// Query- or hash-only navigations stay on the page already passed the checks
	// below. `from.name` must be set, or the initial navigation (from
	// START_LOCATION) to an unnamed route would skip the checks entirely.
	if (from.name && to.name === from.name && to.path === from.path) {
		return next()
	}

	const { userResource } = usersStore()
	let { isLoggedIn } = sessionStore()
	const { settings } = useSettings()

	try {
		if (isLoggedIn) {
			await userResource.promise
		}
	} catch (error) {
		isLoggedIn = false
	}

	if (!isLoggedIn) {
		await settings.promise
		if (!settings.data?.allow_guest_access) {
			window.location.href = '/login'
			return
		}
		// The landing page at / is for guests when the site turns it on. Otherwise
		// a guest at / goes to the course catalog, as before.
		if (to.name === 'Home' && !settings.data?.show_guest_landing) {
			return next({ name: 'Courses' })
		}
	}

	if (to.name === 'Setup' && !userResource.data?.is_system_manager) {
		return next({ name: 'Home' })
	}

	if (
		isLoggedIn &&
		!setupChecked &&
		to.name !== 'Setup' &&
		userResource.data?.is_system_manager
	) {
		try {
			const target = await setupRoute(userResource.data?.developer_mode)
			setupChecked = true
			if (target === false) return next(false)
			if (target) return next(target)
		} catch (_) {
			// Fail open for this navigation; the next one asks again.
		}
	}

	// A new student fills in the registration form before any other page. The
	// state call fails open, and the Registration page itself is always allowed,
	// so the gate cannot loop.
	if (
		isLoggedIn &&
		to.name !== 'Registration' &&
		userResource.data?.is_student &&
		(await useRegistrationState().needsRegistration())
	) {
		return next({ name: 'Registration' })
	}

	return next()
}

// The site root serves this app too (the home_page hook), so Home shows the
// bare domain instead of /lms/. The router keeps its /lms base for every other
// page, and reloading "/" loads the app at Home again.
export function showHomeAtSiteRoot(to) {
	if (to.name !== 'Home' || window.location.pathname === '/') return
	window.history.replaceState(
		window.history.state,
		'',
		'/' + window.location.search + window.location.hash,
	)
}

router.beforeEach(guardNavigation)
router.afterEach(showHomeAtSiteRoot)

export default router
